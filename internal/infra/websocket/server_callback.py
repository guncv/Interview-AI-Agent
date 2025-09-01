from internal.infra.log.logger import logger
from internal.domain.models.websocket import AudioChunkMessage, WebSocketClient, SegmentStartMessage, SegmentEndMessage
from internal.infra.db.redis import redis_client
from internal.infra.stt.gcp_stt import GCP_SpeechToText
from typing import List
from internal.utils.matching import merge_and_split_transcripts
from internal.domain.models.speech_recognize import SpeechRecognize

class WebSocketServerCallback:
    def __init__(self):
        self.stt_client = GCP_SpeechToText()
        self.redis_client = redis_client

    async def handle_segment_start(self, client: WebSocketClient, request: SegmentStartMessage):
        logger.info(f"[Websocket: handle segment start]: Called")
        client.current_segment_id = request.segment_id

    async def handle_audio_chunk(self, client: WebSocketClient, audio_message: AudioChunkMessage):
        logger.info(f"[Websocket: handle audio chunk] Called: audio data: ")
        try:
            prev_chunk = self.redis_client.get_prev_segment_chunk(client.session_id, audio_message.segment_id)
            
            combined_chunks: List[bytes] = []
            if prev_chunk:
                combined_chunks.append(prev_chunk)
            combined_chunks.append(audio_message.audio_data)
            bias_prompt = self.redis_client.get_session_bias_prompt(client.session_id)
            
            logger.info(f"[Websocket: handle audio chunk] Combined chunks length: {len(combined_chunks)}")
            full_transcript: SpeechRecognize = self.stt_client.transcribe_streaming_from_chunks_v2(combined_chunks, client.language, bias_prompt)
            logger.info(f"[Websocket: handle audio chunk] Full transcript: {full_transcript}")
            
            prev_transcript = self.redis_client.get_prev_segment_stt(client.session_id, audio_message.segment_id)

            if prev_transcript:
                logger.info(f"[Websocket: handle audio chunk] Prev transcript found: {prev_transcript}")
                improved_prev, curr_only = merge_and_split_transcripts(prev_transcript, full_transcript, session_id=client.session_id)
                logger.info(f"[Websocket: handle audio chunk] Curr transcript: {curr_only}")
                self.redis_client.save_segment_stt(client.session_id, audio_message.segment_id, improved_prev.transcript)
                self.redis_client.save_prev_segment_stt(client.session_id, audio_message.segment_id, curr_only)
            else:
                logger.info(f"[Websocket: handle audio chunk] All transcripts not found")
                logger.info(f"[Websocket: handle audio chunk] Curr transcript: {full_transcript}")
                self.redis_client.save_prev_segment_stt(client.session_id, audio_message.segment_id, full_transcript)

            self.redis_client.save_prev_segment_chunk(client.session_id, audio_message.segment_id, audio_message.audio_data)

            logger.info(f"[Websocket: handle audio chunk] Final Transcript Saved: {full_transcript}")

        except Exception as e:
            logger.error(f"[Websocket: handle audio chunk] Error: {e}")
            raise e

    async def handle_segment_end(self, client: WebSocketClient, request: SegmentEndMessage):
        logger.info(f"[Websocket: handle segment end]:")
        try:
            prev_transcript = self.redis_client.get_prev_segment_stt(client.session_id, request.segment_id)
            if not prev_transcript:
                logger.info(f"[Websocket: handle segment end]: Segment STT not found")
                return
            
            curr_transcript = self.redis_client.get_segment_stt(client.session_id, request.segment_id)
            curr_transcript.append(prev_transcript.transcript)
            final_transcript = " ".join(curr_transcript)
            logger.info(f"[Websocket: handle segment end] Final joined transcript: {final_transcript}")
            self.redis_client.clear_segment_stt(client.session_id, request.segment_id)
            self.redis_client.clear_prev_segment_stt(client.session_id, request.segment_id)
            self.redis_client.clear_prev_segment_chunk(client.session_id, request.segment_id)
        except Exception as e:
            logger.error(f"[Websocket: handle segment end]: {e}")
            raise e

    