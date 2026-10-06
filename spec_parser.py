"""spec_parser.py — Natural Language Client Brief Interpreter

Hybrid Architecture:
- Live Mode: Anthropic Claude 3.5 Sonnet (claude-3-5-sonnet-20241022) with structured schema enforcement.
- Heuristic Fallback Mode: Deterministic regex and token frequency extractor ensuring
  100% functionality offline, without network access, or when ANTHROPIC_API_KEY is not configured.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)


class ClientSpecification(BaseModel):
    """Pydantic validated technical specification extracted from natural language brief."""

    project_type: str = Field(
        default="Residential", description="Type of project e.g. Residential, Commercial, Interior Fit-out"
    )
    preferred_lighting_brand: Literal["Philips", "Havells", "Wipro", "Syska", "Any"] = "Philips"
    lighting_wattage: int = Field(default=12, description="Target wattage in Watts (e.g. 12, 15)")
    lighting_color_temp: Literal["3000K", "4000K", "6500K"] = "3000K"
    preferred_fan_brand: Literal["Atomberg", "Havells", "Crompton", "Orient", "Any"] = "Atomberg"
    fan_type: Literal["BLDC", "Induction"] = "BLDC"
    preferred_switch_brand: Literal["Schneider", "Legrand", "Havells", "Anchor", "Any"] = "Schneider"
    switch_grade: Literal["Modular", "Smart"] = "Modular"
    flooring_preference: Literal["Vitrified Tile", "Italian Marble", "Granite", "Ceramic"] = "Vitrified Tile"
    paint_preference: Literal["Luxury Emulsion", "Premium Emulsion", "Tractor Emulsion"] = "Luxury Emulsion"
    sanitaryware_brand: Literal["Jaquar", "Kohler", "Hindware", "Any"] = "Jaquar"
    raw_brief: str = ""
    extraction_mode: str = "Deterministic-Heuristic"

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def _extract_heuristically(brief_text: str) -> ClientSpecification:
    """Deterministic offline regex & keyword scoring extractor supporting English & Hinglish vernacular."""
    lower = brief_text.lower()

    # Project Type
    project_type = "Residential Interior"
    if "commercial" in lower or "office" in lower or "retail" in lower or "fit-out" in lower:
        project_type = "Commercial Fit-Out"
    elif "villa" in lower or "bungalow" in lower:
        project_type = "Custom Villa"

    # 1. Lighting Brand
    lighting_brand = "Philips"
    if re.search(r"havells\s+(?:\w+\s+){0,3}(?:light|spot|downlight|panel|led|batti|roshni)", lower) or (
        "havells" in lower and ("spot" in lower or "downlight" in lower or "batti" in lower)
    ):
        lighting_brand = "Havells"
    elif "wipro" in lower:
        lighting_brand = "Wipro"
    elif "syska" in lower:
        lighting_brand = "Syska"
    elif "philips" in lower:
        lighting_brand = "Philips"
    elif "havells" in lower and not re.search(r"havells\s+(?:\w+\s+){0,3}(?:fan|pankh)", lower):
        lighting_brand = "Havells"

    # 2. Lighting Wattage
    wattage = 12
    watt_match = re.search(r"(\d+)\s*(?:w|watt)", lower)
    if watt_match:
        val = int(watt_match.group(1))
        if val in [12, 15, 18, 20, 36]:
            wattage = val if val in [12, 15] else (15 if val < 30 else 12)
        elif val < 14:
            wattage = 12
        else:
            wattage = 15

    # 3. Color Temperature
    cct: Literal["3000K", "4000K", "6500K"] = "3000K"
    if "4000k" in lower or "neutral white" in lower or "daylight" in lower:
        cct = "4000K"
    elif "6500k" in lower or "6000k" in lower or "cool white" in lower or "cool day" in lower:
        cct = "6500K"
    elif "3000k" in lower or "warm white" in lower or "yellow" in lower or "warm" in lower or "peeli" in lower:
        cct = "3000K"

    # 4. Fan Brand & Type
    fan_brand = "Atomberg"
    if re.search(r"orient\s+(?:\w+\s+){0,3}(?:fan|pankh)|(?:fan|pankh)\w*\s+(?:\w+\s+){0,3}orient", lower) or "orient" in lower:
        fan_brand = "Orient"
    elif re.search(r"crompton\s+(?:\w+\s+){0,3}(?:fan|pankh)|(?:fan|pankh)\w*\s+(?:\w+\s+){0,3}crompton", lower) or "crompton" in lower:
        fan_brand = "Crompton"
    elif re.search(r"havells\s+(?:\w+\s+){0,3}(?:fan|pankh)|(?:fan|pankh)\w*\s+(?:\w+\s+){0,3}havells", lower):
        fan_brand = "Havells"
    elif "atomberg" in lower:
        fan_brand = "Atomberg"

    fan_type: Literal["BLDC", "Induction"] = "BLDC"
    if "induction" in lower or "traditional fan" in lower or "standard fan" in lower:
        fan_type = "Induction"
    elif "bldc" in lower or "energy saving" in lower or "remote" in lower or "brushless" in lower:
        fan_type = "BLDC"

    # 5. Switch Brand & Grade
    switch_brand = "Schneider"
    if (
        re.search(r"anchor\s+(?:\w+\s+){0,3}(?:switch|button)|(?:switch|button)\w*\s+(?:\w+\s+){0,3}anchor", lower)
        or "anchor" in lower
        or "panasonic" in lower
    ):
        switch_brand = "Anchor"
    elif re.search(r"legrand\s+(?:\w+\s+){0,3}(?:switch|button)|(?:switch|button)\w*\s+(?:\w+\s+){0,3}legrand", lower) or "legrand" in lower:
        switch_brand = "Legrand"
    elif re.search(r"havells\s+(?:\w+\s+){0,3}(?:switch|button)|(?:switch|button)\w*\s+(?:\w+\s+){0,3}havells", lower):
        switch_brand = "Havells"
    elif "schneider" in lower:
        switch_brand = "Schneider"

    switch_grade: Literal["Modular", "Smart"] = "Modular"
    if "smart" in lower or "wifi" in lower or "alexa" in lower or "automation" in lower:
        switch_grade = "Smart"

    # 6. Flooring Preference
    flooring = "Vitrified Tile"
    if "italian" in lower or "marble" in lower or "botticino" in lower:
        flooring = "Italian Marble"
    elif "granite" in lower:
        flooring = "Granite"
    elif "ceramic" in lower:
        flooring = "Ceramic"
    elif "carpet" in lower or "carpet tile" in lower:
        flooring = "Vitrified Tile"  # Core residential base, with carpet tiles mapped in BOQ
    elif "vitrified" in lower or "tile" in lower or "kajaria" in lower or "somany" in lower or "farsh" in lower:
        flooring = "Vitrified Tile"

    # 7. Paint Preference
    paint = "Luxury Emulsion"
    if "tractor" in lower or "economy" in lower or "budget paint" in lower:
        paint = "Tractor Emulsion"
    elif "royale" in lower or "luxury" in lower or "washable" in lower or "acrylic emulsion" in lower:
        paint = "Luxury Emulsion"
    elif "premium" in lower:
        paint = "Premium Emulsion"

    # 8. Sanitaryware Brand
    sanitary = "Jaquar"
    if "kohler" in lower:
        sanitary = "Kohler"
    elif "hindware" in lower:
        sanitary = "Hindware"
    elif "jaquar" in lower:
        sanitary = "Jaquar"

    return ClientSpecification(
        project_type=project_type,
        preferred_lighting_brand=lighting_brand,
        lighting_wattage=wattage,
        lighting_color_temp=cct,
        preferred_fan_brand=fan_brand,
        fan_type=fan_type,
        preferred_switch_brand=switch_brand,
        switch_grade=switch_grade,
        flooring_preference=flooring,
        paint_preference=paint,
        sanitaryware_brand=sanitary,
        raw_brief=brief_text,
        extraction_mode="Deterministic-Heuristic",
    )


def parse_client_brief(
    brief_text: str,
    api_key: str | None = None,
    groq_api_key: str | None = None,
) -> ClientSpecification:
    """Interprets unstructured natural language client brief into typed ClientSpecification.

    Priority:
    1. Groq LLM (Llama 3.3 70B Versatile) via groq_api_key or GROQ_API_KEY environment variable.
    2. Anthropic Claude 3.5 Sonnet via api_key or ANTHROPIC_API_KEY environment variable.
    3. Deterministic heuristic regex/token parser (zero network / unkeyed fallback).
    """
    if not brief_text or not brief_text.strip():
        return ClientSpecification(raw_brief="")

    # Resolve Groq Key (passed explicitly, via GROQ_API_KEY, or if generic api_key starts with 'gsk_')
    groq_key = groq_api_key or os.environ.get("GROQ_API_KEY")
    if not groq_key and api_key and api_key.strip().startswith("gsk_"):
        groq_key = api_key.strip()

    prompt = f"""You are an expert Indian architectural cost estimator and quantity surveyor.
Extract technical construction and interior specifications from the following client brief:

CLIENT BRIEF:
\"\"\"{brief_text}\"\"\"

Analyze the text and return ONLY a valid, raw JSON object (with NO markdown formatting, NO triple backticks) matching this exact schema:
{{
  "project_type": "Residential" | "Commercial" | "Interior Fit-out",
  "preferred_lighting_brand": "Philips" | "Havells" | "Wipro" | "Syska" | "Any",
  "lighting_wattage": 12 | 15,
  "lighting_color_temp": "3000K" | "4000K" | "6500K",
  "preferred_fan_brand": "Atomberg" | "Havells" | "Crompton" | "Orient" | "Any",
  "fan_type": "BLDC" | "Induction",
  "preferred_switch_brand": "Schneider" | "Legrand" | "Havells" | "Anchor" | "Any",
  "switch_grade": "Modular" | "Smart",
  "flooring_preference": "Vitrified Tile" | "Italian Marble" | "Granite" | "Ceramic",
  "paint_preference": "Luxury Emulsion" | "Premium Emulsion" | "Tractor Emulsion",
  "sanitaryware_brand": "Jaquar" | "Kohler" | "Hindware" | "Any"
}}"""

    # 1. Try Groq (Ultra-Fast Cloud Inference)
    if groq_key and groq_key.strip():
        from groq import Groq

        groq_client = Groq(api_key=groq_key.strip())
        candidate_models = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "llama-3.3-70b-versatile"]

        for model_name in candidate_models:
            try:
                completion = groq_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a professional architectural specification parser. You always output pure JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_completion_tokens=600,
                )

                raw_reply = completion.choices[0].message.content or "{}"
                cleaned = re.sub(r"^```(?:json)?\s*", "", raw_reply)
                cleaned = re.sub(r"\s*```$", "", cleaned).strip()

                parsed_data = json.loads(cleaned)
                parsed_data["raw_brief"] = brief_text
                parsed_data["extraction_mode"] = f"Groq-{model_name.split('/')[-1].upper()}"
                return ClientSpecification(**parsed_data)

            except Exception as e:
                logger.debug("Groq model %s failed: %s. Trying next candidate...", model_name, e)
                continue

    # 2. Try Anthropic Claude 3.5 Sonnet if Groq is not configured
    anthropic_key = api_key if (api_key and not api_key.startswith("gsk_")) else os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key and anthropic_key.strip():
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=anthropic_key.strip())
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=600,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )

            raw_reply = response.content[0].text.strip()
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw_reply)
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()

            parsed_data = json.loads(cleaned)
            parsed_data["raw_brief"] = brief_text
            parsed_data["extraction_mode"] = "Claude-3.5-Sonnet"
            return ClientSpecification(**parsed_data)

        except Exception as e:
            logger.warning("Claude 3.5 Sonnet extraction encountered error: %s. Falling back to heuristic.", e)

    # 3. Default deterministic heuristic fallback
    return _extract_heuristically(brief_text)
