# pyright: reportPrivateUsage=false

"""Test suite for `unstructured.partition.doc` module."""

from __future__ import annotations

import pathlib
from typing import Any, Iterator

import pytest
from pytest_mock import MockFixture

from test_unstructured.unit_utils import (
    ANY,
    CaptureFixture,
    FixtureRequest,
    assert_round_trips_through_JSON,
    example_doc_path,
    method_mock,
)
from unstructured.chunking.basic import chunk_elements
from unstructured.documents.elements import (
    Address,
    CompositeElement,
    Element,
    ListItem,
    NarrativeText,
    Table,
    TableChunk,
    Text,
    Title,
)
from unstructured.partition.doc import partition_doc
from unstructured.partition.docx import partition_docx


def test_partition_doc_matches_partition_docx(request: FixtureRequest):
    doc_file_path = example_doc_path("simple.doc")
    docx_file_path = example_doc_path("simple.docx")

    assert partition_doc(doc_file_path) == partition_docx(docx_file_path)


# -- document-source (file or filename) ----------------------------------------------------------


def test_partition_doc_from_filename(expected_elements: list[Element], capsys: CaptureFixture[str]):
    elements = partition_doc(example_doc_path("simple.doc"))

    assert elements == expected_elements
    assert all(e.metadata.file_directory == example_doc_path("") for e in elements)
    assert capsys.readouterr().out == ""
    assert capsys.readouterr().err == ""


def test_partition_doc_from_file_with_libre_office_filter(
    expected_elements: list[Element], capsys: CaptureFixture[str]
):
    with open(example_doc_path("simple.doc"), "rb") as f:
        elements = partition_doc(file=f, libre_office_filter="MS Word 2007 XML")

    assert elements == expected_elements
    assert capsys.readouterr().out == ""
    assert capsys.readouterr().err == ""


def test_partition_doc_from_file_with_no_libre_office_filter(
    expected_elements: list[Element], capsys: CaptureFixture[str]
):
    with open(example_doc_path("simple.doc"), "rb") as f:
        elements = partition_doc(file=f, libre_office_filter=None)

    assert elements == expected_elements
    assert capsys.readouterr().out == ""
    assert capsys.readouterr().err == ""
    assert all(e.metadata.filename is None for e in elements)


def test_partition_doc_raises_when_both_a_filename_and_file_are_specified():
    doc_file_path = example_doc_path("simple.doc")

    with open(doc_file_path, "rb") as f:
        with pytest.raises(ValueError, match="Exactly one of filename and file must be specified"):
            partition_doc(filename=doc_file_path, file=f)


def test_partition_doc_raises_when_neither_a_file_path_nor_a_file_like_object_are_provided():
    with pytest.raises(ValueError, match="Exactly one of filename and file must be specified"):
        partition_doc()


def test_partition_raises_with_missing_doc(tmp_path: pathlib.Path):
    doc_filename = str(tmp_path / "asdf.doc")

    with pytest.raises(ValueError, match="asdf.doc does not exist"):
        partition_doc(filename=doc_filename)


# -- .metadata.filename --------------------------------------------------------------------------


def test_partition_doc_from_filename_gets_filename_from_filename_arg():
    elements = partition_doc(example_doc_path("simple.doc"))

    assert len(elements) > 0
    assert all(e.metadata.filename == "simple.doc" for e in elements)


def test_partition_doc_from_file_gets_filename_None():
    with open(example_doc_path("simple.doc"), "rb") as f:
        elements = partition_doc(file=f)

    assert len(elements) > 0
    assert all(e.metadata.filename is None for e in elements)


def test_partition_doc_from_filename_prefers_metadata_filename():
    elements = partition_doc(example_doc_path("simple.doc"), metadata_filename="test")

    assert len(elements) > 0
    assert all(element.metadata.filename == "test" for element in elements)


def test_partition_doc_from_file_prefers_metadata_filename():
    with open(example_doc_path("simple.doc"), "rb") as f:
        elements = partition_doc(file=f, metadata_filename="test")

    assert all(e.metadata.filename == "test" for e in elements)


# -- .metadata.filetype --------------------------------------------------------------------------


def test_partition_doc_gets_the_DOC_MIME_type_in_metadata_filetype():
    DOC_MIME_TYPE = "application/msword"
    elements = partition_doc(example_doc_path("simple.doc"))
    assert all(e.metadata.filetype == DOC_MIME_TYPE for e in elements), (
        f"Expected all elements to have '{DOC_MIME_TYPE}' as their filetype, but got:"
        f" {repr(elements[0].metadata.filetype)}"
    )


# -- .metadata.last_modified ---------------------------------------------------------------------


def test_partition_doc_pulls_last_modified_from_filesystem(mocker: MockFixture):
    filesystem_last_modified = "2029-07-05T09:24:28"
    mocker.patch(
        "unstructured.partition.doc.get_last_modified_date", return_value=filesystem_last_modified
    )

    elements = partition_doc(example_doc_path("fake.doc"))

    assert all(e.metadata.last_modified == filesystem_last_modified for e in elements)


def test_partition_doc_prefers_metadata_last_modified_when_provided(
    mocker: MockFixture,
):
    filesystem_last_modified = "2029-07-05T09:24:28"
    metadata_last_modified = "2020-07-05T09:24:28"
    mocker.patch(
        "unstructured.partition.doc.get_last_modified_date", return_value=filesystem_last_modified
    )

    elements = partition_doc(
        example_doc_path("simple.doc"), metadata_last_modified=metadata_last_modified
    )

    assert all(e.metadata.last_modified == metadata_last_modified for e in elements)


# -- language-recognition metadata ---------------------------------------------------------------


def test_partition_doc_adds_languages_metadata():
    elements = partition_doc(example_doc_path("simple.doc"))
    assert all(e.metadata.languages == ["eng"] for e in elements)


def test_partition_doc_respects_detect_language_per_element_arg():
    elements = partition_doc(
        example_doc_path("language-docs/eng_spa_mult.doc"), detect_language_per_element=True
    )
    assert [e.metadata.languages for e in elements] == [
        ["eng"],
        ["spa", "eng"],
        ["eng"],
        ["eng"],
        ["spa"],
    ]


# -- miscellaneous -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "expected_value"),
    [({}, "hi_res"), ({"strategy": None}, "hi_res"), ({"strategy": "auto"}, "auto")],
)
def test_partition_odt_forwards_strategy_arg_to_partition_docx(
    request: FixtureRequest, kwargs: dict[str, Any], expected_value: str | None
):
    from unstructured.partition.docx import _DocxPartitioner

    def fake_iter_document_elements(self: _DocxPartitioner) -> Iterator[Element]:
        yield Text(f"strategy == {self._opts.strategy}")

    _iter_elements_ = method_mock(
        request,
        _DocxPartitioner,
        "_iter_document_elements",
        side_effect=fake_iter_document_elements,
    )

    (element,) = partition_doc(example_doc_path("simple.doc"), **kwargs)

    _iter_elements_.assert_called_once_with(ANY)
    assert element.text == f"strategy == {expected_value}"


def test_partition_doc_grabs_emphasized_texts():
    expected_emphasized_text_contents = ["bold", "italic", "bold-italic", "bold-italic"]
    expected_emphasized_text_tags = ["b", "i", "b", "i"]

    elements = partition_doc(example_doc_path("fake-doc-emphasized-text.doc"))

    assert isinstance(elements[0], Table)
    assert elements[0].metadata.emphasized_text_contents == expected_emphasized_text_contents
    assert elements[0].metadata.emphasized_text_tags == expected_emphasized_text_tags

    assert elements[1] == NarrativeText("I am a bold italic bold-italic text.")
    assert elements[1].metadata.emphasized_text_contents == expected_emphasized_text_contents
    assert elements[1].metadata.emphasized_text_tags == expected_emphasized_text_tags

    assert elements[2] == NarrativeText("I am a normal text.")
    assert elements[2].metadata.emphasized_text_contents is None
    assert elements[2].metadata.emphasized_text_tags is None


def test_partition_doc_round_trips_through_json():
    """Elements produced can be serialized then deserialized without loss."""
    assert_round_trips_through_JSON(partition_doc(example_doc_path("simple.doc")))


def test_partition_doc_chunks_elements_when_chunking_strategy_is_specified():
    document_path = example_doc_path("simple.doc")
    elements = partition_doc(document_path)
    chunks = partition_doc(document_path, chunking_strategy="basic")

    # -- all chunks are chunk element-types --
    assert all(isinstance(c, (CompositeElement, Table, TableChunk)) for c in chunks)
    # -- chunks from partitioning match those produced by chunking elements in separate step --
    assert chunks == chunk_elements(elements)


def test_partition_doc_assigns_deterministic_and_unique_element_ids():
    document_path = example_doc_path("duplicate-paragraphs.doc")

    ids = [element.id for element in partition_doc(document_path)]
    ids_2 = [element.id for element in partition_doc(document_path)]

    # -- ids should match even though partitioned separately --
    assert ids == ids_2
    # -- ids should be unique --
    assert len(ids) == len(set(ids))


# == module-level fixtures =======================================================================


@pytest.fixture()
def expected_elements() -> list[Element]:
    return [
        Title("These are a few of my favorite things:"),
        ListItem("Parrots"),
        ListItem("Hockey"),
        Text("Analysis"),
        NarrativeText("This is my first thought. This is my second thought."),
        NarrativeText("This is my third thought."),
        Text("2023"),
        Address("DOYLESTOWN, PA 18901"),
    ]
