IMAGE_PROMPTS_FROM_NARRATION_TEMPLATE = '''
You are an expert at creating PROMPTS for AI image generation.
Analyze **NARRATION TO ILLUSTRATE** and split the text into {num_segments} segments.
Create clear PROMPTS for Stable Diffusion, that perfectly illustrate each narration segment straight.

- EACH VISUAL PROMPT MUST:
Exactly 10 words.
More than 60 characters is FORBIDDEN
Describe subjects with actions
Describe environment with time period.
Use basic and descriptive words.
Don't describe scene like a story, use individual words.

- CRITICAL PROHIBITED:
Style, lighting.
Abstract concepts.
Maps or diagrams.
Complex words.
Wrong time period.

- MANDATORY OUTPUT FORMAT (STRICT - DO NOT DEVIATE):
You MUST output exactly {num_segments} lines, each starting with "PROMPT" followed by a number and colon.
Each line MUST follow this exact pattern:
PROMPT 1: [your visual prompt text here]
PROMPT 2: [your visual prompt text here]

CRITICAL: Every line must start with "PROMPT" (uppercase) followed by a space, then the number, then a colon and space.
Do NOT use any other format. Do NOT add explanations. Do NOT use markdown or bullets.
Output ONLY the PROMPT lines, nothing else.

Example of correct output:
PROMPT 1: Airplane high sky. Broken car. Old woman screaming.

- NARRATION TO ILLUSTRATE:
{narration_script}.
'''

def get_image_prompt(narration_script, num_segments):
    return IMAGE_PROMPTS_FROM_NARRATION_TEMPLATE.format(
        narration_script=narration_script,
        num_segments=num_segments
    )
