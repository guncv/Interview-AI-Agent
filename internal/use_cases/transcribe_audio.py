class TranscribeAudio:
    def __init__(self, speech_to_text_service):
        self.speech_to_text_service = speech_to_text_service

    def execute(self, audio_data):
        
        return self.speech_to_text_service.transcribe(audio_data)
