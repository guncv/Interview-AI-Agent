from internal.infra.log.logger import logger
from internal.domain.models.websocket import AudioChunkMessage, WebSocketClient, SegmentStartMessage, SegmentEndMessage
from internal.infra.db.redis import redis_client
from internal.infra.stt.gcp_stt import GCP_SpeechToText
from typing import List
from internal.utils.matching import merge_and_split_transcripts
from internal.domain.models.speech_recognize import SpeechRecognize
from internal.infra.stt.whisper_stt import WhisperSpeechToText

class WebSocketServerCallback:
    def __init__(self):
        self.stt_client = GCP_SpeechToText()
        self.whisper_client = WhisperSpeechToText()
        self.redis_client = redis_client

    async def handle_segment_start(self, client: WebSocketClient, request: SegmentStartMessage):
        logger.info(f"[Websocket: handle segment start]: Called")
        client.current_segment_id = request.segment_id

    # async def handle_audio_chunk(self, client: WebSocketClient, audio_message: AudioChunkMessage):
    #     logger.info(f"[Websocket: handle audio chunk] Called: audio data: ")
    #     try:
    #         prev_chunk = self.redis_client.get_prev_segment_chunk(client.session_id, audio_message.segment_id)
    #         bias_prompt = self.redis_client.get_session_bias_prompt(client.session_id)

    #         prev_recognize = None
    #         if prev_chunk:
    #             prev_cache = self.redis_client.get_prev_segment_stt(client.session_id, audio_message.segment_id)
    #             prev_recognize, curr_recognize = self.stt_client.transcribe_streaming_with_context(
    #                 prev_chunk=prev_chunk,
    #                 curr_chunk=audio_message.audio_data,
    #                 language_code=client.language,
    #                 bias_prompt=bias_prompt
    #             )
    #             self.redis_client.save_prev_segment_stt(client.session_id, audio_message.segment_id, curr_recognize)
    #             logger.info(f"[Websocket: handle audio chunk] Prev cache found: '{prev_cache}'")
    #             logger.info(f"[Websocket: handle audio chunk] Prev transcript: '{prev_recognize}'")
    #             logger.info(f"[Websocket: handle audio chunk] Curr transcript: '{curr_recognize}'")
    #         else:
    #             curr_recognize: SpeechRecognize = self.stt_client.transcribe_single_chunk(audio_message.audio_data, client.language, bias_prompt)
    #             self.redis_client.save_prev_segment_stt(client.session_id, audio_message.segment_id, curr_recognize)
    #         logger.info(f"[Websocket: handle audio chunk] Full transcript: '{curr_recognize}'")
            
    #         self.redis_client.save_prev_segment_chunk(client.session_id, audio_message.segment_id, audio_message.audio_data)
    #         if prev_recognize:
    #             self.redis_client.save_segment_stt(client.session_id, audio_message.segment_id, prev_recognize.transcript)
    #             logger.info(f"[Websocket: handle audio chunk] Prev transcript saved on session and segment id: '{client.session_id}_{audio_message.segment_id}'")

    #     except Exception as e:
    #         logger.error(f"[Websocket: handle audio chunk] Error: {e}")
    #         raise e

    async def handle_audio_chunk(self, client: WebSocketClient, audio_message: AudioChunkMessage):
        logger.info(f"[Websocket: handle audio chunk] Called: audio data: ")
        try:
            # prev_chunk = self.redis_client.get_prev_segment_chunk(client.session_id, audio_message.segment_id)
            # bias_prompt = self.redis_client.get_session_bias_prompt(client.session_id)

            # prev_recognize = None
            # if prev_chunk:
            #     prev_cache = self.redis_client.get_prev_segment_stt(client.session_id, audio_message.segment_id)
            #     prev_recognize, curr_recognize = self.stt_client.transcribe_streaming_with_context(
            #         prev_chunk=prev_chunk,
            #         curr_chunk=audio_message.audio_data,
            #         language_code=client.language,
            #         bias_prompt=bias_prompt
            #     )
            #     self.redis_client.save_prev_segment_stt(client.session_id, audio_message.segment_id, curr_recognize)
            #     logger.info(f"[Websocket: handle audio chunk] Prev cache found: '{prev_cache}'")
            #     logger.info(f"[Websocket: handle audio chunk] Prev transcript: '{prev_recognize}'")
            #     logger.info(f"[Websocket: handle audio chunk] Curr transcript: '{curr_recognize}'")
            # else:
            #     curr_recognize: SpeechRecognize = self.stt_client.transcribe_single_chunk(audio_message.audio_data, client.language, bias_prompt)
            #     self.redis_client.save_prev_segment_stt(client.session_id, audio_message.segment_id, curr_recognize)
            # logger.info(f"[Websocket: handle audio chunk] Full transcript: '{curr_recognize}'")
            
            curr_recognize = self.whisper_client.transcribe_audio(audio_message.audio_data)
            logger.info(f"[Websocket: handle audio chunk] Curr transcript: '{curr_recognize}'")
            self.redis_client.save_segment_stt(client.session_id, audio_message.segment_id, curr_recognize.transcript)
            # self.redis_client.save_prev_segment_chunk(client.session_id, audio_message.segment_id, audio_message.audio_data)
            # if prev_recognize:
            #     self.redis_client.save_segment_stt(client.session_id, audio_message.segment_id, prev_recognize.transcript)
            #     logger.info(f"[Websocket: handle audio chunk] Prev transcript saved on session and segment id: '{client.session_id}_{audio_message.segment_id}'")

        except Exception as e:
            logger.error(f"[Websocket: handle audio chunk] Error: {e}")
            raise e


    async def handle_segment_end(self, client: WebSocketClient, request: SegmentEndMessage):
        logger.info(f"[Websocket: handle segment end]:")
        try:
            # prev_transcript = self.redis_client.get_prev_segment_stt(client.session_id, request.segment_id)
            # if not prev_transcript:
            #     logger.info(f"[Websocket: handle segment end]: Segment STT not found")
            #     return
            
            # logger.info(f"[Websocket: handle segment end]: Getting segment STT from session and segment id: '{client.session_id}_{request.segment_id}'")
            curr_transcript = self.redis_client.get_segment_stt(client.session_id, request.segment_id)
            # if curr_transcript:
            #     curr_transcript.append(prev_transcript.transcript)
            # else:
            #     curr_transcript = [prev_transcript.transcript]
            final_transcript = " ".join(curr_transcript)
            logger.info(f"[Websocket: handle segment end] Final joined transcript: {final_transcript}")
            self.redis_client.clear_segment_stt(client.session_id, request.segment_id)
            # self.redis_client.clear_prev_segment_stt(client.session_id, request.segment_id)
            # self.redis_client.clear_prev_segment_chunk(client.session_id, request.segment_id)
        except Exception as e:
            logger.error(f"[Websocket: handle segment end]: {e}")
            raise e

    