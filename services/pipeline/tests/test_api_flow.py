"""End-to-end through the API: from a source document to a published chart."""

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from .conftest import FakeProvider, make_token

Headers = Callable[..., dict[str, str]]

TEXT = (
    "Heute arbeiten rund 12 000 Personen in der Musterbranche. "
    "Die Initiative würde die Kosten bis 2035 verdoppeln. "
    "Das ist schlicht unfair."
)
VOTE = {
    "id": "2099-01-01-example",
    "date": "2099-01-01",
    "title": "Musterinitiative (synthetisch)",
    "kind": "popular_initiative",
    "official_url": "https://example.org/vote",
}
CHART: dict[str, Any] = {
    "title": "Beschäftigte in der Musterbranche",
    "description": "Anzahl Beschäftigte pro Jahr, 2020 bis 2022.",
    "spec": {
        "mark": "bar",
        "data": {"values": [{"year": "2020", "n": 11000}, {"year": "2022", "n": 12000}]},
        "encoding": {"x": {"field": "year", "type": "ordinal"}, "y": {"field": "n", "type": "quantitative"}},
    },
    "data_sources": [
        {
            "publisher": "Example Office",
            "title": "Table 1",
            "url": "https://example.org/t1",
            "accessed_at": "2099-01-01",
        }
    ],
}


def _setup_claims(client: TestClient, as_user: Headers, fake_llm: FakeProvider) -> dict[str, dict[str, Any]]:
    admin = as_user("admin")
    assert client.post("/api/votes", json=VOTE, headers=admin).status_code == 201
    doc = client.post(
        f"/api/votes/{VOTE['id']}/documents",
        json={
            "kind": "booklet",
            "side": "opponents",
            "title": "Erläuterungen, S. 12",
            "url": "https://example.org/b",
            "text": TEXT,
        },
        headers=admin,
    ).json()
    fake_llm.response = {
        "claims": [
            {
                "quote": "Heute arbeiten rund 12 000 Personen in der Musterbranche.",
                "class": "fact",
                "rationale": "Present, measurable state.",
            },
            {
                "quote": "Die Initiative würde die Kosten bis 2035 verdoppeln.",
                "class": "fact",
                "rationale": "Wrongly labelled; a reviewer will correct this.",
            },
            {"quote": "Das ist schlicht unfair.", "class": "opinion", "rationale": "Value judgement."},
            {"quote": "Ein erfundener Satz.", "class": "fact", "rationale": "Not in the text."},
        ]
    }
    run = client.post(f"/api/documents/{doc['id']}/extract", headers=admin).json()
    assert (run["accepted"], len(run["rejected"])) == (3, 1)

    # Running it again must not duplicate claims.
    client.post(f"/api/documents/{doc['id']}/extract", headers=admin)
    claims = client.get(f"/api/votes/{VOTE['id']}", headers=admin).json()["claims"]
    assert len(claims) == 3
    return {c["quote"].split()[1]: c for c in claims}  # keyed by their second word


def test_from_document_to_published_chart(
    client: TestClient, as_user: Headers, fake_llm: FakeProvider
) -> None:
    claims = _setup_claims(client, as_user, fake_llm)
    fact, forecast, opinion = claims["arbeiten"], claims["Initiative"], claims["ist"]
    reviewer, visualizer, admin = as_user("reviewer"), as_user("visualizer"), as_user("admin")

    # Reviewer corrects the misclassified forecast; it needs an estimate_by to be approved.
    response = client.post(
        f"/api/claims/{forecast['id']}/review",
        json={"status": "approved", "class": "forecast"},
        headers=reviewer,
    )
    assert response.status_code == 422
    response = client.post(
        f"/api/claims/{forecast['id']}/review",
        json={"status": "approved", "class": "forecast", "estimate_by": "Gegnerkomitee"},
        headers=reviewer,
    )
    assert response.json()["class"] == "forecast"
    assert response.json()["proposed_class"] == "fact"
    client.post(f"/api/claims/{opinion['id']}/review", json={"status": "rejected"}, headers=reviewer)

    # No chart for a claim that isn't an approved fact yet.
    assert (
        client.post(f"/api/claims/{fact['id']}/visualizations", json=CHART, headers=visualizer).status_code
        == 409
    )
    client.post(f"/api/claims/{fact['id']}/review", json={"status": "approved"}, headers=reviewer)

    # Publishing is blocked while the fact has no chart.
    blocked = client.post(f"/api/votes/{VOTE['id']}/publish", headers=admin)
    assert blocked.status_code == 409
    assert "without an approved chart" in " ".join(blocked.json()["problems"])

    viz = client.post(f"/api/claims/{fact['id']}/visualizations", json=CHART, headers=visualizer).json()
    assert (
        client.post(f"/api/visualizations/{viz['id']}/submit", headers=visualizer).json()["status"]
        == "in_review"
    )

    # Visualizers can't review; and a reviewer who edited the chart can't either (four eyes).
    assert (
        client.post(
            f"/api/visualizations/{viz['id']}/review", json={"decision": "approve"}, headers=visualizer
        ).status_code
        == 403
    )
    both = as_user("reviewer", "visualizer", email="visualizer@stimmig.test")
    four_eyes = client.post(
        f"/api/visualizations/{viz['id']}/review", json={"decision": "approve"}, headers=both
    )
    assert four_eyes.status_code == 403
    assert "four-eyes" in four_eyes.json()["detail"]

    approved = client.post(
        f"/api/visualizations/{viz['id']}/review", json={"decision": "approve"}, headers=reviewer
    )
    assert approved.json()["status"] == "approved"

    # Not public before publishing.
    assert client.get(f"/public/v1/votes/{VOTE['id']}").status_code == 404
    assert client.post(f"/api/votes/{VOTE['id']}/publish", headers=admin).json()["status"] == "published"

    public = client.get(f"/public/v1/votes/{VOTE['id']}")
    assert public.headers["cache-control"].startswith("public")
    body = public.json()
    assert [f["quote"] for f in body["facts"]] == [fact["quote"]]
    assert body["facts"][0]["visualizations"][0]["title"] == CHART["title"]
    assert body["facts"][0]["source"]["document"] == "Erläuterungen, S. 12"
    assert [(f["quote"], f["estimate_by"]) for f in body["forecasts"]] == [
        (forecast["quote"], "Gegnerkomitee")
    ]
    assert "Das ist schlicht unfair." not in public.text
    assert client.get("/public/v1/votes").json()[0]["visualization_count"] == 1

    actions = [e["action"] for e in client.get(f"/api/votes/{VOTE['id']}/audit", headers=admin).json()]
    assert {"vote.publish", "visualization.approve", "claim.approved", "extraction.run"} <= set(actions)


def test_remote_data_in_a_chart_is_rejected(
    client: TestClient, as_user: Headers, fake_llm: FakeProvider
) -> None:
    fact = _setup_claims(client, as_user, fake_llm)["arbeiten"]
    client.post(f"/api/claims/{fact['id']}/review", json={"status": "approved"}, headers=as_user("reviewer"))
    remote = {**CHART, "spec": {"mark": "bar", "data": {"url": "https://example.org/data.csv"}}}
    response = client.post(
        f"/api/claims/{fact['id']}/visualizations", json=remote, headers=as_user("visualizer")
    )
    assert response.status_code == 422


def test_permissions_are_enforced(client: TestClient, as_user: Headers) -> None:
    assert client.get("/api/votes").status_code == 401
    assert client.post("/api/votes", json=VOTE, headers=as_user("visualizer")).status_code == 403
    assert client.post("/api/votes", json=VOTE, headers=as_user("reviewer")).status_code == 403
    assert client.get("/api/votes", headers=as_user("visualizer")).status_code == 200

    me = client.get("/api/me", headers=as_user("reviewer")).json()
    assert me["roles"] == ["reviewer"]
    assert "claims:review" in me["permissions"]
    assert "votes:publish" not in me["permissions"]

    # A user without any known role can't even read.
    assert client.get("/api/votes", headers=as_user("guest")).status_code == 403


def test_bad_tokens_are_rejected(client: TestClient) -> None:
    wrong_audience = make_token(["admin"], audience="urn:stimmig:identity")
    expired = make_token(["admin"], expires_in=-60)
    for token in (wrong_audience, expired, "not-a-jwt"):
        response = client.get("/api/votes", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401, token
