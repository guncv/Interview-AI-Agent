from internal.infra.log.logger import logger
from internal.domain.models.websocket import AudioChunkMessage, WebSocketClient, SegmentStartMessage, SegmentEndMessage
from internal.infra.db.redis import redis_client
from internal.infra.stt.gcp_stt import GCP_SpeechToText
from typing import List
from internal.utils.matching import remove_fuzzy_overlap

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

            logger.info(f"[Websocket: handle audio chunk] Combined chunks length: {len(combined_chunks)}")
            full_transcript: str = self.stt_client.transcribe_streaming_from_chunks(combined_chunks, client.language)
            logger.info(f"[Websocket: handle audio chunk] Full transcript: {full_transcript}")
            
            all_transcripts = self.redis_client.get_segment_stt(client.session_id, audio_message.segment_id)

            if all_transcripts:
                prev_transcript = all_transcripts[-1]
                logger.info(f"[Websocket: handle audio chunk] Prev transcript found: {prev_transcript}")
                curr_transcript = remove_fuzzy_overlap(prev_transcript, full_transcript)
                logger.info(f"[Websocket: handle audio chunk] Curr transcript: {curr_transcript}")
            else:
                logger.info(f"[Websocket: handle audio chunk] All transcripts not found")
                curr_transcript = full_transcript
                logger.info(f"[Websocket: handle audio chunk] Curr transcript: {curr_transcript}")

            self.redis_client.save_segment_stt(client.session_id, audio_message.segment_id, curr_transcript)
            self.redis_client.save_prev_segment_chunk(client.session_id, audio_message.segment_id, audio_message.audio_data)

            logger.info(f"[Websocket: handle audio chunk] Final Transcript Saved: {full_transcript} and {curr_transcript}")

        except Exception as e:
            logger.error(f"[Websocket: handle audio chunk] Error: {e}")
            raise e

    async def handle_segment_end(self, client: WebSocketClient, request: SegmentEndMessage):
        logger.info(f"[Websocket: handle segment end]:")
        try:
            chunk_data_list = self.redis_client.get_segment_stt(client.session_id, request.segment_id)
            if not chunk_data_list:
                logger.info(f"[Websocket: handle segment end]: Segment STT not found")
                return
            
            final_transcript = " ".join(chunk_data_list)
            logger.info(f"[Websocket: handle segment end] Final joined transcript: {final_transcript}")
            self.redis_client.clear_segment_stt(client.session_id, request.segment_id)
        except Exception as e:
            logger.error(f"[Websocket: handle segment end]: {e}")
            raise e

    