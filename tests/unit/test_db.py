"""DB layer tests — no LLM key required."""
import json

from sqlalchemy.orm import Session

from db.models import PartRow, RunRow, VersionRow


def test_run_row_roundtrip(_isolated_db):
    with Session(_isolated_db) as s:
        run = RunRow(input_text="hello world")
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        fetched = s.get(RunRow, run_id)
        assert fetched is not None
        assert fetched.input_text == "hello world"
        assert fetched.status == "pending"
        assert fetched.output_text is None


def test_run_row_status_update(_isolated_db):
    with Session(_isolated_db) as s:
        run = RunRow(input_text="test")
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        run.status = "completed"
        run.output_text = "some output"
        s.commit()

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        assert run.status == "completed"
        assert run.output_text == "some output"


def test_part_and_version_roundtrip(_isolated_db):
    """A part with a v1 version persists the full schema and reloads."""
    with Session(_isolated_db) as s:
        run = RunRow(input_text="a 60x40x10 bracket", status="completed")
        s.add(run)
        s.flush()
        run_id = run.id

        part = PartRow(title="a 60x40x10 bracket", latest_version=1)
        s.add(part)
        s.flush()
        part_id = part.id

        version = VersionRow(
            part_id=part_id,
            version_number=1,
            parent_version_id=None,
            source="generate",
            prompt="a 60x40x10 bracket",
            model_id="gemini-3.1-flash-lite",
            code_path=f"artifacts/code/part_{part_id}/v1.py",
            stl_path=f"artifacts/exports/part_{part_id}/part_v1.stl",
            step_path=f"artifacts/exports/part_{part_id}/part_v1.step",
            thumbnail_path=None,
            repair_count=0,
            token_usage=json.dumps({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
            cost_usd=0.0001,
            run_id=run_id,
        )
        s.add(version)
        s.commit()
        version_id = version.id

    with Session(_isolated_db) as s:
        v = s.get(VersionRow, version_id)
        assert v is not None
        assert v.version_number == 1
        assert v.parent_version_id is None
        assert v.source == "generate"
        assert v.thumbnail_path is None  # nullable, populated in Phase 2
        assert v.repair_count == 0
        assert json.loads(v.token_usage)["total_tokens"] == 15
        assert v.cost_usd == 0.0001

        part = s.get(PartRow, v.part_id)
        assert part.title == "a 60x40x10 bracket"
        assert part.latest_version == 1


def test_version_chain_self_fk(_isolated_db):
    """parent_version_id links a v2 to its v1 parent (the modification chain)."""
    with Session(_isolated_db) as s:
        run = RunRow(status="completed")
        s.add(run)
        s.flush()
        part = PartRow(title="chain", latest_version=2)
        s.add(part)
        s.flush()

        v1 = VersionRow(
            part_id=part.id, version_number=1, source="generate",
            code_path="c1", stl_path="s1", step_path="st1", repair_count=0, run_id=run.id,
        )
        s.add(v1)
        s.flush()
        v2 = VersionRow(
            part_id=part.id, version_number=2, parent_version_id=v1.id, source="modify",
            code_path="c2", stl_path="s2", step_path="st2", repair_count=0, run_id=run.id,
        )
        s.add(v2)
        s.commit()

        chain = (
            s.query(VersionRow)
            .filter(VersionRow.part_id == part.id)
            .order_by(VersionRow.version_number)
            .all()
        )
        assert [v.version_number for v in chain] == [1, 2]
        assert chain[1].parent_version_id == chain[0].id
