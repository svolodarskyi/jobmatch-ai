from unittest.mock import MagicMock, patch

from supabase import Client

from app.db import get_db


def test_get_db_yields_client() -> None:
    """get_db should yield a Supabase Client without making a live network call."""
    mock_client = MagicMock(spec=Client)

    with patch("app.db.create_client", return_value=mock_client) as mock_create:
        gen = get_db()
        yielded = next(gen)

        # Verify create_client was called with the settings values
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args.args[0] == "https://test.supabase.co"
        assert call_args.args[1] == "test-supabase-key"

        # Verify the yielded object is the client returned by create_client
        assert yielded is mock_client

        # Exhaust the generator (no cleanup expected, but should not raise)
        try:
            next(gen)
        except StopIteration:
            pass
