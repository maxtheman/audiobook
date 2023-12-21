import pytest
from audiobook import setup_tts, describe_image, chunk_text, concatenate_audio_pydub, make_page_reading, Page, PydanticPage
import os
import base64
import tempfile
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

load_dotenv()

import shutil

@pytest.fixture
def setup_files():
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()

    # Create a temporary image file
    temp_image = os.path.join(temp_dir, 'test_image.jpg')
    with open(temp_image, 'wb') as f:
        f.write(b'This is a test image file')

    # Create a temporary audio file
    temp_audio = os.path.join(temp_dir, 'test_audio.wav')
    with open(temp_audio, 'w') as f:
        f.write('This is a test audio file')

    yield temp_image, temp_audio

    # Clean up the temporary directory after the test is done
    shutil.rmtree(temp_dir)

@pytest.fixture
def setup_page_image():
    # Create the required directory structure
    required_dir = 'outputs/pages/0/image'
    os.makedirs(required_dir, exist_ok=True)

    # Create a temporary image file
    temp_image = os.path.join(required_dir, 'page.png')
    with open(temp_image, 'wb') as f:
        f.write(b'This is a test image file')

    yield temp_image

@pytest.fixture
def setup_audio_files():
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()

    # Create a temporary audio file
    temp_audio = os.path.join(temp_dir, '1.wav')
    with open(temp_audio, 'w') as f:
        f.write('This is a test audio file')

    # Create another temporary audio file
    temp_audio2 = os.path.join(temp_dir, '2.wav')
    with open(temp_audio2, 'w') as f:
        f.write('This is another test audio file')

    yield temp_dir

    # Clean up the temporary directory after the test is done
    shutil.rmtree(temp_dir)

def test_setup_tts(setup_files):
    tts = setup_tts()
    assert tts is not None

def test_interpret_image(setup_files):
    '''also mocks and tests the LLM calls'''
    image_uri, _ = setup_files
    figure_name = "Test Figure"
    surrounding_text = "This is a test surrounding text"
    model = "gpt-4-vision-preview"
    mode = "specific_image"

    # Mock the response from the external service
    mock_choice = MagicMock()
    mock_choice.message.content = "Mocked description of the image"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    # Base64 encode the image content
    image_content = base64.b64encode(b'This is a test image file').decode('utf-8')

    # Use patch to mock the external service call
    with patch('audiobook.completion', return_value=mock_response) as mock_completion:
        response = describe_image(image_uri, figure_name, surrounding_text, model, mode)
        # Check that the mock was called with the correct arguments
        mock_completion.assert_called_once_with(
            model=model,
            max_tokens=4000,
            messages=[{
                "content": [
                    "Please describe the picture named Test Figure on this page. How is it related to the following text? Text: Test Figure Describe its importance to the passage, in detail. Describe the image directly as if you were writing a description in a book, e.g., say 'the image is' instead of 'the image you shared is', for example.",
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_content}"}}
                ],
                "role": "user"
            }],
        )
        assert response == "Mocked description of the image"

def test_chunk_text(setup_files):
    text = "This is a test text"
    max_length = 10
    page_image, _ = setup_files
    described_figures = set()
    handle_figures = True
    chunks, described_figures = chunk_text(text, max_length, page_image, described_figures, handle_figures)
    assert chunks is not None
    assert described_figures is not None

def test_concatenate_audio_pydub(setup_audio_files):
    path = setup_audio_files
    output_file_name = 'output.wav'
    verbose = 1

    # Create a mock AudioSegment
    mock_audio_segment = MagicMock()

    # Use patch to mock the AudioSegment.from_file method
    with patch('pydub.AudioSegment.from_file', return_value=mock_audio_segment):
        try:
            concatenate_audio_pydub(path, output_file_name, verbose)
            assert True
        except Exception as e:
            print(e)
            assert False

def test_page_reading(setup_files, setup_page_image):
    path, _ = setup_files
    tts = setup_tts()
    page_start = 0
    page_end = 1

    # Create a mock AudioSegment
    mock_audio_segment = MagicMock()

    # Mock the tts.tts_to_file method
    tts.tts_to_file = MagicMock()

    # Mock the fitz.open function
    mock_fitz_open = MagicMock()
    mock_pages = [MagicMock() for _ in range(page_end - page_start)]
    for mock_page in mock_pages:
        mock_page.get_text.return_value = 'This is a test page text'
    mock_fitz_open.return_value = mock_pages

    # Create a mock Doc instance
    mock_doc = MagicMock()

    with patch('pydub.AudioSegment.from_file', return_value=mock_audio_segment), \
         patch('fitz.open', return_value=mock_fitz_open):
        try:
            # Update the function call to match the new implementation
            make_page_reading(mock_doc, tts, mock_fitz_open, page_start)
            assert True
        except Exception as e:
            print(e)
            assert False

def test_page_methods(setup_files, setup_page_image):
    path, _ = setup_files
    tts = setup_tts()
    page_start = 0
    page_end = 1

    # Create a mock AudioSegment
    mock_audio_segment = MagicMock()

    # Mock the tts.tts_to_file method
    tts.tts_to_file = MagicMock()

    # Mock the fitz.open function
    mock_fitz_open = MagicMock()

    # Mock the Document object
    mock_doc = MagicMock()

    # Mock the Page object from the Document
    mock_page = MagicMock()
    mock_page.get_text.return_value = 'This is a test page text'

    # Set the return value of the Document's page method to the mock Page
    mock_doc.load_page.return_value = mock_page

    # Set the return value of fitz.open to the mock Document
    mock_fitz_open.return_value = mock_doc

    with patch('pydub.AudioSegment.from_file', return_value=mock_audio_segment), \
         patch('fitz.open', return_value=mock_fitz_open):
        try:
            page = Page(mock_doc, page_start)
            assert page.page_number == page_start
            assert page.page_audio_uri is not None
            assert page.page_image_uri is not None
            assert page.page_text is not None
            assert page.cleaned_text is not None
            assert page.figures == []

            figure_names = page.extract_figure_names()
            assert isinstance(figure_names, list)

            image_present = page.check_if_image_is_present('Figure 1.1')
            assert isinstance(image_present, bool)

            combined_text = page.combine_cleaned_text_and_descriptions()
            assert isinstance(combined_text, str)

            pydantic_page = page.return_pydantic_page()
            assert isinstance(pydantic_page, PydanticPage)
            assert pydantic_page.page_number == page_start
            assert pydantic_page.page_text is not None
            assert pydantic_page.page_image_uri is not None
            assert pydantic_page.page_audio_uri is not None
            assert pydantic_page.figures == []

            assert str(page) == page.page_text
            assert True
        except Exception as e:
            print(e)
            assert False