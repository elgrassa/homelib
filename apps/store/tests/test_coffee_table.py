"""WP07 Coffee Table + progress named red tests — specs/coffee-table.md."""

from __future__ import annotations

from pathlib import Path

from apps.store import coffee_table as ct
from apps.store import progress_ops as prog
from apps.store.sqlite import connect, migrate, seed


def _db(tmp_path: Path):
    path = tmp_path / "coffee.sqlite"
    conn = connect(path)
    migrate(conn)
    seed(conn, repo_root=Path(__file__).resolve().parents[3])
    return conn


def test_acceptance_required_before_queued(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    try:
        books = [str(r[0]) for r in conn.execute("SELECT book_id FROM books LIMIT 2")]
        assert len(books) >= 2
        ct.propose_items(conn, principal_id="local-user", resource_ids=books)
        playlist = ct.get_playlist(conn, "local-user")
        assert all(i.status is ct.PlaylistStatus.PROPOSED for i in playlist.items)
        accepted = ct.accept_proposed(
            conn, principal_id="local-user", accept_item_ids=[playlist.items[0].id]
        )
        statuses = {i.id: i.status for i in accepted.items}
        assert statuses[playlist.items[0].id] is ct.PlaylistStatus.QUEUED
        assert statuses[playlist.items[1].id] is ct.PlaylistStatus.PROPOSED
    finally:
        conn.close()


def test_manual_survives_regeneration(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    try:
        books = [str(r[0]) for r in conn.execute("SELECT book_id FROM books LIMIT 3")]
        assert len(books) >= 2
        regen_target = books[2] if len(books) > 2 else books[1]
        ct.add_item(
            conn,
            principal_id="local-user",
            resource_id=books[0],
            origin=ct.PlaylistOrigin.MANUAL_SHELF,
        )
        ct.propose_items(conn, principal_id="local-user", resource_ids=[books[1]])
        ct.regenerate_proposals(conn, principal_id="local-user", resource_ids=[regen_target])
        playlist = ct.get_playlist(conn, "local-user")
        manuals = [i for i in playlist.items if i.manual]
        assert len(manuals) == 1
        assert manuals[0].resource_id == books[0]
        assert manuals[0].status is ct.PlaylistStatus.QUEUED
    finally:
        conn.close()


def test_no_silent_reinsert_of_completed_or_removed(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    try:
        books = [str(r[0]) for r in conn.execute("SELECT book_id FROM books LIMIT 2")]
        pl = ct.add_item(
            conn,
            principal_id="local-user",
            resource_id=books[0],
            origin=ct.PlaylistOrigin.MANUAL_SHELF,
        )
        ct.patch_items(
            conn,
            principal_id="local-user",
            updates=[{"id": pl.items[0].id, "status": "completed"}],
        )
        pl2 = ct.add_item(
            conn,
            principal_id="local-user",
            resource_id=books[1],
            origin=ct.PlaylistOrigin.MANUAL_SHELF,
        )
        removed_id = next(i.id for i in pl2.items if i.resource_id == books[1])
        ct.remove_item(conn, principal_id="local-user", item_id=removed_id)
        ct.propose_items(conn, principal_id="local-user", resource_ids=books)
        after = ct.get_playlist(conn, "local-user")
        proposed_ids = {
            i.resource_id for i in after.items if i.status is ct.PlaylistStatus.PROPOSED
        }
        assert books[0] not in proposed_ids
        assert books[1] not in proposed_ids
    finally:
        conn.close()


def test_remove_keeps_resource(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    try:
        book_id = str(conn.execute("SELECT book_id FROM books LIMIT 1").fetchone()[0])
        pl = ct.add_item(
            conn,
            principal_id="local-user",
            resource_id=book_id,
            origin=ct.PlaylistOrigin.MANUAL_SHELF,
        )
        ct.remove_item(conn, principal_id="local-user", item_id=pl.items[0].id)
        assert conn.execute("SELECT 1 FROM books WHERE book_id = ?", (book_id,)).fetchone()
        visible = ct.get_playlist(conn, "local-user")
        assert all(i.id != pl.items[0].id for i in visible.items)
    finally:
        conn.close()


def test_independent_read_listen_progress(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    try:
        book_id = str(conn.execute("SELECT book_id FROM books LIMIT 1").fetchone()[0])
        prog.upsert_progress(
            conn,
            principal_id="local-user",
            event=prog.ProgressEvent(
                resource_id=book_id, kind=prog.ProgressKind.READ, char_offset=10
            ),
        )
        prog.upsert_progress(
            conn,
            principal_id="local-user",
            event=prog.ProgressEvent(
                resource_id=book_id, kind=prog.ProgressKind.LISTEN, char_offset=99
            ),
        )
        read = prog.get_progress(
            conn, principal_id="local-user", resource_id=book_id, kind=prog.ProgressKind.READ
        )
        listen = prog.get_progress(
            conn,
            principal_id="local-user",
            resource_id=book_id,
            kind=prog.ProgressKind.LISTEN,
        )
        assert read is not None and read["char_offset"] == 10
        assert listen is not None and listen["char_offset"] == 99
    finally:
        conn.close()


def test_restart_persists_playlist_and_progress(tmp_path: Path) -> None:
    path = tmp_path / "persist.sqlite"
    conn = connect(path)
    migrate(conn)
    seed(conn, repo_root=Path(__file__).resolve().parents[3])
    book_id = str(conn.execute("SELECT book_id FROM books LIMIT 1").fetchone()[0])
    pl = ct.add_item(
        conn,
        principal_id="local-user",
        resource_id=book_id,
        origin=ct.PlaylistOrigin.MANUAL_SHELF,
    )
    ct.set_last_opened(conn, principal_id="local-user", item_id=pl.items[0].id)
    prog.upsert_progress(
        conn,
        principal_id="local-user",
        event=prog.ProgressEvent(resource_id=book_id, kind=prog.ProgressKind.READ, char_offset=42),
    )
    conn.close()

    again = connect(path)
    try:
        playlist = ct.get_playlist(again, "local-user")
        assert playlist.last_opened_item_id == pl.items[0].id
        assert playlist.items[0].ordinal == 0
        read = prog.get_progress(
            again, principal_id="local-user", resource_id=book_id, kind=prog.ProgressKind.READ
        )
        assert read is not None and read["char_offset"] == 42
    finally:
        again.close()
