from benchy.runner.baseline import build_prompt, parse_reply, run_baseline
from benchy.runner.clients import MeteredClient
from benchy.suite import prepare_workspace


class OneReply:
    name = "stub"
    context_tokens = 8192

    def __init__(self, reply):
        self.reply = reply

    def chat(self, messages, **kw):
        return self.reply

    def health(self):
        return True

    def unload(self):
        pass


def test_parse_reply_variants():
    reply = (
        "Here you go.\n\nFILE: src/a.py\n```python\nx = 1\n```\n\n"
        "**FILE: `src/b.py`**\n```\ny = 2\n```\n"
    )
    assert parse_reply(reply) == [("src/a.py", "x = 1\n"), ("src/b.py", "y = 2\n")]


def test_prompt_contains_task_and_files(chunk_task, tmp_path):
    ws = tmp_path / "w"
    prepare_workspace(chunk_task, ws)
    prompt = build_prompt(chunk_task.request, ws, chunk_task.project_files())
    assert chunk_task.request in prompt and "src/listkit/chunks.py" in prompt
    assert "test_hidden" not in prompt and "solution" not in prompt


def test_paths_outside_the_workspace_are_refused(chunk_task, tmp_path):
    ws = tmp_path / "w"
    prepare_workspace(chunk_task, ws)
    reply = "FILE: ../escape.py\n```python\nboom\n```\nFILE: /etc/x\n```\nboom\n```\nFILE: .git/config\n```\nx\n```\n"
    out = run_baseline(MeteredClient(OneReply(reply)), "t", ws, chunk_task.project_files())
    assert out.status == "no_change" and len(out.rejected_paths) == 3
    assert not (tmp_path / "escape.py").exists()


def test_unparsable_and_model_errors(chunk_task, tmp_path):
    ws = tmp_path / "w"
    prepare_workspace(chunk_task, ws)
    assert (
        run_baseline(MeteredClient(OneReply("I think it is fine")), "t", ws, []).status
        == "unparsable"
    )

    class Boom(OneReply):
        def chat(self, messages, **kw):
            raise ConnectionError("server down")

    out = run_baseline(MeteredClient(Boom("")), "t", ws, [])
    assert out.status == "error" and "server down" in out.message


def test_deadline_gives_timeout(chunk_task, tmp_path):
    ws = tmp_path / "w"
    prepare_workspace(chunk_task, ws)
    out = run_baseline(MeteredClient(OneReply("x"), deadline=0.0), "t", ws, [])
    assert out.status == "timeout"


def test_usage_is_metered():
    client = MeteredClient(OneReply("abcdefg"))
    client.chat([{"role": "user", "content": "1234567"}], temperature=0.2, max_tokens=10, tag="t")
    assert client.usage.calls == 1
    assert client.usage.prompt_tokens_est == 2 and client.usage.completion_tokens_est == 2
