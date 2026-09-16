from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from app.core.exceptions import ApplicationError
from app.services.document_deletion import DocumentDeletionService


def test_uses_one_timestamp_for_the_document() -> None:
    deleted_at = datetime(2026, 9, 16, 12, tzinfo=UTC)
    store = Mock()
    store.soft_delete_document.return_value = 3

    result = DocumentDeletionService(store, clock=lambda: deleted_at).delete("doc")

    assert result.document_id == "doc"
    assert result.soft_deleted_chunks == 3
    store.soft_delete_document.assert_called_once_with("doc", deleted_at=deleted_at)


def test_unknown_document_is_a_controlled_404() -> None:
    store = Mock()
    store.soft_delete_document.return_value = None

    with pytest.raises(ApplicationError) as error:
        DocumentDeletionService(store).delete("missing")

    assert error.value.status_code == 404
    assert error.value.code == "document_not_found"
