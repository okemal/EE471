import io
import json
import os
import sys
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from speech import SpeechError, azure_request, recognize, synthesize


def wav_audio(rate=16000, channels=1):
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b'\0\0' * rate * channels)
    return output.getvalue()


class SpeechTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch('speech.azure_request')
    def test_recognition_preserves_lexical_command_words(self, azure):
        azure.return_value = json.dumps({'RecognitionStatus': 'Success', 'NBest': [
            {'Lexical': 'three plus five is', 'Display': '3 + 5 is.'}]}).encode()
        response = self.client.post('/api/speech/recognize', data=wav_audio(), content_type='audio/wav')
        self.assertEqual(response.json, {'text': 'three plus five is'})
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    @patch('speech.azure_request')
    def test_invalid_audio_never_reaches_azure(self, azure):
        for audio in (b'not wav', wav_audio(rate=8000), wav_audio(channels=2)):
            with self.subTest(length=len(audio)):
                response = self.client.post('/api/speech/recognize', data=audio, content_type='audio/wav')
                self.assertEqual(response.status_code, 400)
        azure.assert_not_called()

    def test_recognition_requires_wav(self):
        self.assertEqual(self.client.post('/api/speech/recognize', json={}).status_code, 400)

    @patch('speech.azure_request', return_value=b'{"RecognitionStatus":"NoMatch"}')
    def test_no_match_is_actionable(self, azure):
        response = self.client.post('/api/speech/recognize', data=wav_audio(), content_type='audio/wav')
        self.assertEqual(response.status_code, 422)
        self.assertIn('try again', response.json['error'])

    @patch('speech.azure_request', return_value=b'not json')
    def test_malformed_upstream_response_is_sanitized(self, azure):
        with self.assertRaises(SpeechError):
            recognize(wav_audio())

    @patch('speech.azure_request', return_value=b'mp3-audio')
    def test_synthesis_returns_audio(self, azure):
        response = self.client.post('/api/speech/speak', json={'text': 'is eight'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'audio/mpeg')
        self.assertIn(b'is eight', azure.call_args.args[2])

    @patch('speech.azure_request')
    def test_synthesis_rejects_markup_and_invalid_input(self, azure):
        for text in (None, '', '<speak>injection</speak>', 'x' * 201, 123):
            self.assertEqual(self.client.post('/api/speech/speak', json={'text': text}).status_code, 400)
        azure.assert_not_called()

    @patch.dict(os.environ, {'AZURE_API_KEY_1': 'test-secret-do-not-expose', 'AZURE_SPEECH_REGION': 'eastus'})
    @patch('speech.urlopen')
    def test_upstream_failures_never_expose_credentials(self, opening):
        for error in (HTTPError('https://example.invalid', 401, 'test-secret-do-not-expose', {}, None),
                      URLError('test-secret-do-not-expose'), TimeoutError('test-secret-do-not-expose')):
            opening.side_effect = error
            response = self.client.post('/api/speech/speak', json={'text': 'three'})
            self.assertEqual(response.status_code, 502)
            self.assertNotIn('test-secret-do-not-expose', response.get_data(as_text=True))

    @patch.dict(os.environ, {'AZURE_API_KEY_1': '', 'AZURE_SPEECH_KEY': ''})
    def test_missing_configuration_is_actionable(self):
        response = self.client.post('/api/speech/speak', json={'text': 'three'})
        self.assertEqual(response.status_code, 503)

    def test_arithmetic_and_division_by_zero(self):
        for operator, operands, expected in [('+', [3, 5], 8), ('-', [3, 5], -2),
                                              ('*', [3, 5], 15), ('/', [3, 5], 0.6)]:
            response = self.client.post('/api/calculate', json={'operator': operator, 'operands': operands})
            self.assertEqual(response.json['result'], expected)
        self.assertEqual(self.client.post('/api/calculate', json={'operator': '/', 'operands': [3, 0]}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
