from core.questions import guidance_text


def test_guidance_keeps_boolean_literal_question():
    literal = guidance_text({"literal_question": {"type": "noul", "noul": True}})
    subtext = guidance_text({"literal_question": {"type": "noul", "noul": False}})

    assert "字面意思：是" in literal
    assert "字面意思：否（有潜台词）" in subtext


def test_guidance_combines_choice_and_score():
    text = guidance_text({
        "true_intent": {"type": "choice", "choice": "confirm_you_care"},
        "best_action": {"type": "choice", "choice": "check_history"},
        "danger_level": {"type": "score", "score": 6.4},
    })

    assert "希望确认你在意" in text
    assert "先核对聊天记录" in text
    assert "紧张度：6/9" in text
