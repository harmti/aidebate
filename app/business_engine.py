import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from app.debate_engine import (
    LLM_OPTIONS,
    get_llm_function,
)

# Get logger
logger = logging.getLogger("aidebate")


# Define the structure for a business idea
class BusinessIdea:
    def __init__(self, title: str, description: str, target_market: str, monetization: str):
        self.title = title
        self.description = description
        self.target_market = target_market
        self.monetization = monetization
        self.critique = {}
        self.refinement = ""
        self.score = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "target_market": self.target_market,
            "monetization": self.monetization,
            "critique": self.critique,
            "refinement": self.refinement,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BusinessIdea":
        idea = cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            target_market=data.get("target_market", ""),
            monetization=data.get("monetization", ""),
        )
        idea.critique = data.get("critique", {})
        idea.refinement = data.get("refinement", "")
        idea.score = data.get("score", 0.0)
        return idea


def generate_business_ideas(
    topic: str,
    generator_llm: str,
    num_ideas: int = 3,
    progress_callback: Optional[Callable[[str, str], None]] = None,
) -> List[BusinessIdea]:
    """
    Generate business ideas based on a topic.

    Args:
        topic: The topic to generate business ideas for
        generator_llm: The LLM to use for idea generation
        num_ideas: Number of ideas to generate
        progress_callback: Optional callback function for progress updates

    Returns:
        List of BusinessIdea objects
    """
    logger.info(f"Generating {num_ideas} business ideas on topic: '{topic}'")

    if progress_callback:
        progress_callback("generating", f"Generating {num_ideas} business ideas using {generator_llm}...")

    generator = get_llm_function(generator_llm)
    if not generator:
        logger.error(f"Invalid LLM selection: {generator_llm}")
        raise ValueError(f"Invalid LLM selection. Please use one of: {', '.join(LLM_OPTIONS)}")

    # Create the prompt for idea generation
    prompt = f"""
    Generate {num_ideas} innovative business ideas related to: {topic}

    For each idea, provide the following in JSON format:
    1. A catchy title
    2. A detailed description of the business concept
    3. The target market
    4. Potential monetization strategies

    Format your response as a valid JSON array with objects containing these fields:
    [
      {{
        "title": "Business Idea Title",
        "description": "Detailed description of the business concept...",
        "target_market": "Description of the target market...",
        "monetization": "Explanation of monetization strategies..."
      }},
      ...
    ]

    Be creative, practical, and ensure each idea is distinct from the others.
    """

    start_time = time.time()
    try:
        response = generator(prompt)
        logger.info(f"Business ideas generated in {time.time() - start_time:.2f} seconds")

        # Extract JSON from the response
        try:
            # Find JSON content in the response (it might be surrounded by text)
            json_start = response.find("[")
            json_end = response.rfind("]") + 1

            if json_start >= 0 and json_end > json_start:
                json_content = response[json_start:json_end]
                ideas_data = json.loads(json_content)

                # Convert to BusinessIdea objects
                ideas = [
                    BusinessIdea(
                        title=idea.get("title", "Untitled Idea"),
                        description=idea.get("description", ""),
                        target_market=idea.get("target_market", ""),
                        monetization=idea.get("monetization", ""),
                    )
                    for idea in ideas_data
                ]

                return ideas[:num_ideas]  # Ensure we only return the requested number
            else:
                # Fallback if JSON parsing fails
                logger.warning("Failed to extract JSON from response, creating generic ideas")
                return [
                    BusinessIdea(
                        title=f"Business Idea {i + 1}",
                        description="Could not parse idea details from LLM response.",
                        target_market="Unknown",
                        monetization="Unknown",
                    )
                    for i in range(num_ideas)
                ]
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from LLM response, creating generic ideas")
            return [
                BusinessIdea(
                    title=f"Business Idea {i + 1}",
                    description="Could not parse idea details from LLM response.",
                    target_market="Unknown",
                    monetization="Unknown",
                )
                for i in range(num_ideas)
            ]
    except Exception as e:
        logger.error(f"Error generating business ideas: {str(e)}")
        raise ValueError(f"Error getting response from {generator_llm}: {str(e)}")


def critique_business_ideas(
    ideas: List[BusinessIdea],
    topic: str,
    critic_llm: str,
    progress_callback: Optional[Callable[[str, str], None]] = None,
) -> List[BusinessIdea]:
    """
    Critique business ideas based on various factors.

    Args:
        ideas: List of BusinessIdea objects to critique
        topic: The original topic
        critic_llm: The LLM to use for critique
        progress_callback: Optional callback function for progress updates

    Returns:
        Updated list of BusinessIdea objects with critique information
    """
    logger.info(f"Critiquing {len(ideas)} business ideas")

    critic = get_llm_function(critic_llm)
    if not critic:
        logger.error(f"Invalid LLM selection: {critic_llm}")
        raise ValueError(f"Invalid LLM selection. Please use one of: {', '.join(LLM_OPTIONS)}")

    for i, idea in enumerate(ideas):
        if progress_callback:
            progress_callback("critiquing", f"Critiquing idea {i + 1}/{len(ideas)} using {critic_llm}...")

        # Create the prompt for idea critique
        prompt = f"""
        Critically evaluate the following business idea related to: {topic}

        BUSINESS IDEA:
        Title: {idea.title}
        Description: {idea.description}
        Target Market: {idea.target_market}
        Monetization: {idea.monetization}

        Provide a detailed critique in JSON format with the following aspects:
        1. Feasibility (1-10 score with explanation)
        2. Market potential (1-10 score with explanation)
        3. Technical complexity (1-10 score with explanation, where 1 is extremely complex and 10 is very simple)
        4. Monetization viability (1-10 score with explanation)
        5. Competitive landscape (list at least 3 potential competitors if applicable)
        6. Overall score (1-10)
        7. Key strengths (list at least 2)
        8. Key weaknesses (list at least 2)
        9. Improvement suggestions (list at least 2)

        Format your response as a valid JSON object:
        {{
          "feasibility": {{ "score": 7, "explanation": "..." }},
          "market_potential": {{ "score": 8, "explanation": "..." }},
          "technical_complexity": {{ "score": 6, "explanation": "..." }},
          "monetization_viability": {{ "score": 7, "explanation": "..." }},
          "competitive_landscape": ["Competitor 1", "Competitor 2", "Competitor 3"],
          "overall_score": 7.5,
          "key_strengths": ["Strength 1", "Strength 2"],
          "key_weaknesses": ["Weakness 1", "Weakness 2"],
          "improvement_suggestions": ["Suggestion 1", "Suggestion 2"]
        }}
        """

        start_time = time.time()
        try:
            response = critic(prompt)
            logger.info(f"Idea {i + 1} critiqued in {time.time() - start_time:.2f} seconds")

            # Extract JSON from the response
            try:
                # Find JSON content in the response
                json_start = response.find("{")
                json_end = response.rfind("}") + 1

                if json_start >= 0 and json_end > json_start:
                    json_content = response[json_start:json_end]
                    critique_data = json.loads(json_content)

                    # Update the idea with critique information
                    idea.critique = critique_data
                    idea.score = critique_data.get("overall_score", 0.0)
                else:
                    logger.warning(f"Failed to extract JSON from critique response for idea {i + 1}")
                    idea.critique = {"error": "Failed to parse critique"}
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON from critique response for idea {i + 1}")
                idea.critique = {"error": "Failed to parse critique"}
        except Exception as e:
            logger.error(f"Error critiquing idea {i + 1}: {str(e)}")
            idea.critique = {"error": f"Error during critique: {str(e)}"}

    return ideas


def refine_business_ideas(
    ideas: List[BusinessIdea],
    topic: str,
    refiner_llm: str,
    progress_callback: Optional[Callable[[str, str], None]] = None,
) -> List[BusinessIdea]:
    """
    Refine business ideas based on critique.

    Args:
        ideas: List of BusinessIdea objects to refine
        topic: The original topic
        refiner_llm: The LLM to use for refinement
        progress_callback: Optional callback function for progress updates

    Returns:
        Updated list of BusinessIdea objects with refinement information
    """
    logger.info(f"Refining {len(ideas)} business ideas")

    refiner = get_llm_function(refiner_llm)
    if not refiner:
        logger.error(f"Invalid LLM selection: {refiner_llm}")
        raise ValueError(f"Invalid LLM selection. Please use one of: {', '.join(LLM_OPTIONS)}")

    for i, idea in enumerate(ideas):
        if progress_callback:
            progress_callback("refining", f"Refining idea {i + 1}/{len(ideas)} using {refiner_llm}...")

        # Skip refinement if critique is missing or has an error
        if not idea.critique or "error" in idea.critique:
            logger.warning(f"Skipping refinement for idea {i + 1} due to missing critique")
            idea.refinement = "Refinement skipped due to missing critique."
            continue

        # Extract improvement suggestions and weaknesses from critique
        suggestions = idea.critique.get("improvement_suggestions", [])
        weaknesses = idea.critique.get("key_weaknesses", [])

        # Create the prompt for idea refinement
        prompt = f"""
        Refine the following business idea related to: {topic}

        ORIGINAL BUSINESS IDEA:
        Title: {idea.title}
        Description: {idea.description}
        Target Market: {idea.target_market}
        Monetization: {idea.monetization}

        CRITIQUE SUMMARY:
        Weaknesses: {", ".join(weaknesses)}
        Improvement Suggestions: {", ".join(suggestions)}

        Please provide a refined version of this business idea that addresses the weaknesses and incorporates
        the improvement suggestions. Keep the same basic concept but enhance it.

        Your response should include:
        1. A refined title (if needed)
        2. An improved description
        3. A more focused target market (if applicable)
        4. Enhanced monetization strategies
        5. A brief explanation of how this refinement addresses the critique

        Format your response in plain text, not as JSON.
        """

        start_time = time.time()
        try:
            response = refiner(prompt)
            logger.info(f"Idea {i + 1} refined in {time.time() - start_time:.2f} seconds")
            idea.refinement = response
        except Exception as e:
            logger.error(f"Error refining idea {i + 1}: {str(e)}")
            idea.refinement = f"Error during refinement: {str(e)}"

    return ideas


def rank_business_ideas(
    ideas: List[BusinessIdea],
    topic: str,
    judge_llm: str,
    progress_callback: Optional[Callable[[str, str], None]] = None,
) -> List[BusinessIdea]:
    """
    Rank business ideas based on their potential.

    Args:
        ideas: List of BusinessIdea objects to rank
        topic: The original topic
        judge_llm: The LLM to use for ranking
        progress_callback: Optional callback function for progress updates

    Returns:
        Sorted list of BusinessIdea objects by rank
    """
    logger.info(f"Ranking {len(ideas)} business ideas")

    if progress_callback:
        progress_callback("ranking", f"Ranking business ideas using {judge_llm}...")

    judge = get_llm_function(judge_llm)
    if not judge:
        logger.error(f"Invalid LLM selection: {judge_llm}")
        raise ValueError(f"Invalid LLM selection. Please use one of: {', '.join(LLM_OPTIONS)}")

    # Prepare ideas summary for ranking
    ideas_summary = []
    for i, idea in enumerate(ideas):
        idea_summary = {
            "id": i,
            "title": idea.title,
            "description": idea.description,
            "target_market": idea.target_market,
            "monetization": idea.monetization,
            "critique_score": idea.score,
            "key_strengths": idea.critique.get("key_strengths", []) if idea.critique else [],
            "key_weaknesses": idea.critique.get("key_weaknesses", []) if idea.critique else [],
            "has_refinement": bool(idea.refinement and "Error" not in idea.refinement),
        }
        ideas_summary.append(idea_summary)

    # Create the prompt for idea ranking
    prompt = f"""
    Rank the following business ideas related to: {topic}

    BUSINESS IDEAS:
    {json.dumps(ideas_summary, indent=2)}

    Analyze each idea and provide a final ranking based on:
    1. Overall business viability
    2. Market potential
    3. Innovation factor
    4. Execution feasibility
    5. Competitive advantage

    For each idea (referenced by ID), provide:
    1. A final score (1-10)
    2. A brief explanation for the ranking

    Format your response as a valid JSON array:
    [
      {{
        "id": 0,
        "final_score": 8.5,
        "explanation": "This idea ranks highly because..."
      }},
      ...
    ]

    Sort the ideas from highest to lowest score in your response.
    """

    start_time = time.time()
    try:
        response = judge(prompt)
        logger.info(f"Ideas ranked in {time.time() - start_time:.2f} seconds")

        # Extract JSON from the response
        try:
            # Find JSON content in the response
            json_start = response.find("[")
            json_end = response.rfind("]") + 1

            if json_start >= 0 and json_end > json_start:
                json_content = response[json_start:json_end]
                ranking_data = json.loads(json_content)

                # Update scores based on ranking
                for rank_info in ranking_data:
                    idea_id = rank_info.get("id")
                    if idea_id is not None and 0 <= idea_id < len(ideas):
                        ideas[idea_id].score = rank_info.get("final_score", ideas[idea_id].score)
                        # Add the explanation to the idea
                        if "explanation" in rank_info:
                            if not ideas[idea_id].critique:
                                ideas[idea_id].critique = {}
                            ideas[idea_id].critique["ranking_explanation"] = rank_info["explanation"]

                # Sort ideas by score (descending)
                ideas.sort(key=lambda x: x.score, reverse=True)
            else:
                logger.warning("Failed to extract JSON from ranking response")
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from ranking response")
    except Exception as e:
        logger.error(f"Error ranking ideas: {str(e)}")

    return ideas


def run_business_idea_generation(
    topic: str,
    generator_llm: str,
    critic_llm: str,
    refiner_llm: str,
    judge_llm: str,
    num_ideas: int = 3,
    progress_callback: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    """
    Run the complete business idea generation, critique, refinement, and ranking process.

    Args:
        topic: The topic to generate business ideas for
        generator_llm: The LLM to use for idea generation
        critic_llm: The LLM to use for critique
        refiner_llm: The LLM to use for refinement
        judge_llm: The LLM to use for ranking
        num_ideas: Number of ideas to generate
        progress_callback: Optional callback function for progress updates

    Returns:
        Dictionary with business idea generation results
    """
    logger.info(f"Starting business idea generation for topic: '{topic}'")

    results = {"ideas": [], "topic": topic}

    # Step 1: Generate ideas
    if progress_callback:
        progress_callback("step1", "Step 1: Generating business ideas...")

    ideas = generate_business_ideas(topic, generator_llm, num_ideas, progress_callback)

    # Step 2: Critique ideas
    if progress_callback:
        progress_callback("step2", "Step 2: Critiquing business ideas...")

    ideas = critique_business_ideas(ideas, topic, critic_llm, progress_callback)

    # Step 3: Refine ideas
    if progress_callback:
        progress_callback("step3", "Step 3: Refining business ideas...")

    ideas = refine_business_ideas(ideas, topic, refiner_llm, progress_callback)

    # Step 4: Rank ideas
    if progress_callback:
        progress_callback("step4", "Step 4: Ranking business ideas...")

    ideas = rank_business_ideas(ideas, topic, judge_llm, progress_callback)

    # Convert ideas to dictionaries for the result
    results["ideas"] = [idea.to_dict() for idea in ideas]

    if progress_callback:
        progress_callback("completed", "Business idea generation completed successfully!")

    logger.info("Business idea generation completed successfully")
    return results
