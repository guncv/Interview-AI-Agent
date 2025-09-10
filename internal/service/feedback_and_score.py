from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_core.output_parsers import JsonOutputParser
from internal.domain.models.interview import FeedbackAndScoreRequest, FeedbackAndScoreResponse, CriteriaScore
from internal.service.prompts.feedback_prompt import FEEDBACK_AND_SCORING_PROMPT
from internal.shared.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.adapters.log.logger import logger
from internal.adapters.llm.loader import loadLLM

def build_criteria_descriptions(criteria_list):
    return "\n".join(
        f"- **{c.criterion_name}** (ID: {c.criterion_id}, Code: {c.criterion_code}): {c.criterion_description_md} (Weight: {c.criterion_weight}, Max Score: {c.criterion_max_score})"
        for c in criteria_list
    )

class FeedbackAndScoreService:
    def __init__(self):
        self.llm = loadLLM("interview")
        self.parser = JsonOutputParser()

        self.prompt = FEEDBACK_AND_SCORING_PROMPT
        self.chain: Runnable = self.prompt | self.llm | self.parser

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

            result = await self.chain.ainvoke(inputs)

            logger.info(f"[Feedback and Score Service Result]: {result}")
            
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
                    criteria_scores.append(CriteriaScore(
                        criterion_id=item.get("criterion_id", "unknown"),
                        criterion_code=item.get("criterion_code", ""),
                        criterion_name=item.get("criterion_name", ""),
                        criterion_score=item["criterion_score"],
                        criterion_feedback=item["criterion_feedback"]
                    ))
            
            return FeedbackAndScoreResponse(
                overall_score=result["overall_score"],
                overall_feedback=result["overall_feedback"],
                criteria_scores=criteria_scores
            )

        except Exception as e:
            logger.error(f"[Feedback and Score Service Error]: {e}")
            raise InterviewSimulationException(
                error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                description=f"[{type(e).__name__}]: {str(e)}"
            )
