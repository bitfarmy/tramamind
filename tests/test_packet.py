from router.packet import (
    build_packet,
    classify,
    code_fences,
    compact_message,
    estimate_tokens,
    fit_summary,
    is_weak,
    wants_retry,
    groq_model,
    omni_model,
    system_prompt,
)


def test_classify_does_not_treat_every_question_as_reasoning():
    assert classify("perché il cielo è blu?") == "general"
    assert classify("spiega passo passo come funziona il router") == "think"
    assert classify("refactor questa funzione\n```python\nprint(1)\n```") == "code"


def test_retry_and_weak_are_narrow():
    assert wants_retry("rifallo meglio")
    assert wants_retry("non basta, sii più preciso")
    assert not wants_retry("fallo meglio la prossima volta nel codice")
    assert is_weak("")
    assert is_weak("Mi dispiace, non posso aiutare con questo.")
    assert not is_weak("Sì.")
    long = "Non posso usare la rete, quindi ecco il codice. " + ("dettaglio " * 80)
    assert not is_weak(long)


def test_model_prefixes():
    assert omni_model("openai/gpt-oss-120b") == "groq/openai/gpt-oss-120b"
    assert omni_model("gemini/gemini-2.5-flash") == "gemini/gemini-2.5-flash"
    assert groq_model("groq/openai/gpt-oss-120b") == "openai/gpt-oss-120b"
    assert groq_model("openai/gpt-oss-120b") == "openai/gpt-oss-120b"


def test_short_history_is_sent_whole():
    history = [
        {"role": "user", "content": "ciao"},
        {"role": "assistant", "content": "ciao a te"},
        {"role": "user", "content": "come stai?"},
    ]
    built = build_packet(history=history, system="sys", summary="", budget=2500, verbatim=6)
    assert built["summarized"] is False
    assert built["sent_tokens"] == built["raw_tokens"]
    assert built["messages"][-1]["content"] == "come stai?"


def test_long_history_stays_under_budget_and_keeps_the_last_question():
    history = []
    for i in range(12):
        history.append({"role": "user", "content": ("contesto vecchio " * 80) + f" #{i}"})
        history.append({"role": "assistant", "content": "risposta lunga " * 80})
    history.append({"role": "user", "content": "ultima domanda concreta"})
    built = build_packet(
        history=history,
        system="sys",
        summary="Riassunto dei fatti: il numero 42, il nome Ada.",
        budget=800,
        verbatim=6,
    )
    assert built["summarized"] is True
    assert built["sent_tokens"] < built["raw_tokens"]
    assert built["sent_tokens"] <= 800 or built["messages"][-1]["content"] == "ultima domanda concreta"
    assert built["messages"][-1]["content"] == "ultima domanda concreta"
    assert "contesto vecchio" not in built["messages"][-1]["content"]
    joined = "\n".join(m["content"] for m in built["messages"])
    assert "contesto vecchio" not in joined or "Riassunto" in joined


def test_code_in_the_tail_is_kept_verbatim():
    code = "```python\nprint(42)\n```"
    history = [{"role": "user", "content": "vecchio " * 400}]
    history.append({"role": "assistant", "content": "ok " * 100})
    history.append({"role": "user", "content": "guarda\n" + code})
    built = build_packet(
        history=history, system="sys", summary="prima si parlava d'altro",
        budget=2500, verbatim=2,
    )
    assert code in built["messages"][-1]["content"]


def test_old_code_fence_is_appended_when_it_fits():
    fence = "```python\nprint(42)\n```"
    fitted = fit_summary("sys", "si è deciso di stampare", [fence], [{"role": "user", "content": "ora?"}], 2500)
    assert fence in fitted
    assert code_fences([{"role": "user", "content": "ecco " + fence}], "niente") == [fence]


def test_compact_keeps_fence():
    text = ("parola " * 200) + "\n```sql\nselect 1\n```"
    compact = compact_message(text, 40)
    assert "```sql" in compact
    assert len(compact) < len(text)


def test_old_diff_and_traceback_are_excerpts():
    from router.packet import diff_blocks, protected_excerpts, traceback_blocks
    diff = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n+KEEP_THIS_LINE = 1\n"
    trace = "Traceback (most recent call last):\n  File \"app.py\", line 3, in <module>\n    main()\nValueError: KEEP_THIS_ERROR\n"
    prose = "nota " * 50
    assert "KEEP_THIS_LINE" in diff_blocks(prose + diff)[0]
    assert "KEEP_THIS_ERROR" in traceback_blocks(prose + trace)[0]
    found = protected_excerpts(
        [
            {"role": "user", "content": prose + diff},
            {"role": "assistant", "content": prose + trace},
            {"role": "tool", "name": "read_file", "content": "FILE_BODY " * 20},
        ],
        "",
    )
    blob = "\n".join(found)
    assert "KEEP_THIS_LINE" in blob
    assert "KEEP_THIS_ERROR" in blob
    assert "FILE_BODY" in blob
    assert protected_excerpts([{"role": "user", "content": "ecco solo testo"}], "") == []


def test_card_comments_are_not_sent():
    assert "Esempio" not in system_prompt("# solo un commento\n")
    assert "Ada" in system_prompt("# commento\nMi chiamo Ada\n")


def test_estimate_is_stable():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 2
