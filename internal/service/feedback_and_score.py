from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_core.output_parsers import JsonOutputParser
from internal.domain.models.interview import FeedbackAndScoreRequest, FeedbackAndScoreResponse, CriteriaScore, GetOverallSummaryRequest, GetOverallSummaryResponse, PreProcessedCriteriaResp, PostProcessedCriteriaResp, PostProcessedCriteria
from internal.service.prompts.feedback_prompt import FEEDBACK_AND_SCORING_PROMPT
from internal.service.prompts.overall_summary_prompt import GET_OVERALL_SUMMARY_PROMPT
from internal.service.prompts.criteria_summary_prompt import CRITERIA_SUMMARY_PROMPT
from internal.shared.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.adapters.log.logger import logger
from internal.adapters.llm.loader import loadLLM, getLLMModel

def build_criteria_descriptions(criteria_list):
    return "\n".join(
        f"- **{c.criterion_name}** (ID: {c.criterion_id}, Code: {c.criterion_code}): {c.criterion_description_md} (Weight: {c.criterion_weight}, Max Score: {c.criterion_max_score})"
        for c in criteria_list
    )

class FeedbackAndScoreService:
    def __init__(self):
        self.llm = loadLLM("interview")
        self.llm_model = getLLMModel()
        self.parser = JsonOutputParser()

        self.feedback_and_score_prompt = FEEDBACK_AND_SCORING_PROMPT
        self.overall_summary_prompt = GET_OVERALL_SUMMARY_PROMPT
        self.criteria_summary_prompt = CRITERIA_SUMMARY_PROMPT
        self.feedback_and_score_chain: Runnable = self.feedback_and_score_prompt | self.llm | self.parser
        self.overall_summary_chain: Runnable = self.overall_summary_prompt | self.llm
        self.criteria_summary_chain: Runnable = self.criteria_summary_prompt | self.llm | self.parser

    async def feedback_and_score(self, request: FeedbackAndScoreRequest) -> FeedbackAndScoreResponse:
        logger.info(f"[Feedback and Score Service Called:]")

        try:
            criteria_descriptions = build_criteria_descriptions(request.criteria)
            max_score = max(float(c.criterion_max_score) for c in request.criteria)
            
            criteria_map = {
                (c.criterion_code, c.criterion_name): c
                for c in request.criteria
            }

            inputs = {
                "rubric_name": request.rubric_name,
                "rubric_description_md": request.rubric_description_md,
                "criteria_descriptions": criteria_descriptions,
                "interviewer_message": request.interviewer_message,
                "user_message": request.user_message,
                "max_score": int(max_score),
            }

            result = await self.feedback_and_score_chain.ainvoke(inputs)
            
            criteria_scores = []
            for item in result["criteria_scores"]:
                key = (item.get("criterion_code", ""), item.get("criterion_name", ""))
                if key in criteria_map:
                    criterion = criteria_map[key]
                    criteria_scores.append(CriteriaScore(
                        criterion_id=criterion.criterion_id,
                        criterion_code=criterion.criterion_code,
                        criterion_name=criterion.criterion_name,
                        criterion_score=item["criterion_score"],
                        criterion_feedback=item["criterion_feedback"]
                    ))
                else:
                    logger.warning(f"Could not map criterion: {item.get('criterion_code', 'N/A')} - {item.get('criterion_name', 'N/A')}")
            
            total_weighted_score = 0
            total_weight = 0
            
            for criteria_score in criteria_scores:
                original_criterion = next(
                    (c for c in request.criteria if c.criterion_id == criteria_score.criterion_id), 
                    None
                )
                if original_criterion:
                    weight = float(original_criterion.criterion_weight)
                    total_weighted_score += criteria_score.criterion_score * weight
                    total_weight += weight
            
            overall_score = total_weighted_score / total_weight if total_weight > 0 else 0
            formatted_score = int(overall_score) if overall_score.is_integer() else round(overall_score, 2)
            
            return FeedbackAndScoreResponse(
                overall_score=formatted_score,
                overall_feedback=result["overall_feedback"],
                criteria_scores=criteria_scores,
                improvement_sentence=result["improvement_sentence"],
                llm_model=self.llm_model
            )

        except Exception as e:
            logger.error(f"[Feedback and Score Service Error]: {e}")
            raise InterviewSimulationException(
                error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                description=f"[{type(e).__name__}]: {str(e)}"
            )

    async def get_overall_summary(self, request: GetOverallSummaryRequest) -> GetOverallSummaryResponse:
        logger.info(f"[Get Overall Summary Service Called:]")

        try:
            summary_list = "\n\n".join([f"**Summary {i+1}:**\n{summary}" for i, summary in enumerate(request.summary_md)])
            prompt_request = {
                "summary_list": summary_list
            }
            
            result = await self.overall_summary_chain.ainvoke(prompt_request)
            
            return GetOverallSummaryResponse(overall_summary_md=result.content)
        except Exception as e:
            logger.error(f"[Get Overall Summary Service Error]: {e}")
            raise InterviewSimulationException(
                error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                description=f"[{type(e).__name__}]: {str(e)}"
            )
            
    async def get_criteria_comments(self, request: PreProcessedCriteriaResp) -> PostProcessedCriteriaResp:
        logger.info(f"[Get Criteria Comments Service Called:]")

        try:
            criteria_data = []
            for criteria in request.criteria:
                comments_text = "\n".join([f"- {comment}" for comment in criteria.criteria_comment])
                criteria_data.append({
                    "criteria_id": criteria.criteria_id,
                    "criteria_name": criteria.criteria_name,
                    "criteria_avg_score": criteria.criteria_avg_score,
                    "comments": comments_text
                })
            
            formatted_criteria = "\n\n".join([
                f"**Criteria ID:** {c['criteria_id']}\n"
                f"**Criteria Name:** {c['criteria_name']}\n"
                f"**Average Score:** {c['criteria_avg_score']}\n"
                f"**Comments:**\n{c['comments']}"
                for c in criteria_data
            ])
            
            prompt_request = {
                "criteria_data": formatted_criteria
            }
            
            result = await self.criteria_summary_chain.ainvoke(prompt_request)
            logger.info(f"[Get Criteria Comments Service Result]: {result}")
            
            original_criteria_map = {
                criteria.criteria_id: criteria for criteria in request.criteria
            }
            
            processed_criteria = []
            for criteria_data in result["criteria"]:
                criteria_id = criteria_data["criteria_id"]
                original_criteria = original_criteria_map.get(criteria_id)
                
                if original_criteria:
                    processed_criteria.append(PostProcessedCriteria(
                        criteria_id=original_criteria.criteria_id,
                        criteria_name=original_criteria.criteria_name,
                        criteria_avg_score=original_criteria.criteria_avg_score,
                        criteria_comment=criteria_data["criteria_comment"]
                    ))
                else:
                    logger.warning(f"Could not find original criteria for ID: {criteria_id}")
            
            return PostProcessedCriteriaResp(criteria=processed_criteria)
            
        except Exception as e:
            logger.error(f"[Get Criteria Comments Service Error]: {e}")
            raise InterviewSimulationException(
                error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                description=f"[{type(e).__name__}]: {str(e)}"
            )