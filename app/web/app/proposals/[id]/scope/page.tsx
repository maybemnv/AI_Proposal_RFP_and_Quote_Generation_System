"use client";

import {use, useEffect, useRef, useState} from "react";

import {AppShell} from "@/components/AppShell";
import {Button} from "@/components/Button";
import {FlagList} from "@/components/FlagList";
import {api, ApiError, type ValidationFlag} from "@/lib/api";
import {demoScope, versionIdForRoute} from "@/lib/demoData";

type PageProps = {params: Promise<{id: string}>};

export default function ScopePage({params}: PageProps) {
  const {id} = use(params);
  const [scope, setScope] = useState<any>(demoScope);
  const [question, setQuestion] = useState<string | null>(demoScope.openQuestions[0]);
  const [resolved, setResolved] = useState(false);
  const resolvedRef = useRef(false);
  const [resolution, setResolution] = useState("");
  const [flags, setFlags] = useState<ValidationFlag[]>([]);
  const [showResolver, setShowResolver] = useState(false);

  useEffect(() => {
    api.get<any>(`/v1/proposal-versions/${versionIdForRoute(id)}`).then((response) => {
      if (response.scope) {
        setScope(response.scope);
        if (response.scope.openQuestions?.length && !resolvedRef.current) setQuestion(response.scope.openQuestions[0]);
      }
    }).catch(() => setFlags([{code: "API_UNAVAILABLE", severity: "blocking", message: "Fixture API unavailable; displayed scope is read-only."}]));
  }, [id]);

  async function resolveQuestion() {
    if (!question) return;
    const selectedQuestion = question;
    setFlags([]);
    try {
      const response = await api.post<any>(`/v1/proposal-versions/${versionIdForRoute(id)}/scope/resolve`, {openQuestion: selectedQuestion, resolution});
      resolvedRef.current = true;
      setScope(response);
      setQuestion(null); setResolved(true); setShowResolver(false); setResolution("");
    } catch (error) {
      setFlags(error instanceof ApiError && error.flags.length ? error.flags : [{code: "API_UNAVAILABLE", severity: "blocking", message: "The fixture API could not save this resolution."}]);
    }
  }

  return <AppShell><div className="workspace-page">
    <div className="page-heading"><div><p className="eyebrow">Scope / {id}</p><h1>Make the work explicit.</h1><p className="lede">Deliverables, milestones, assumptions, exclusions, and questions all stay visible before pricing.</p></div><span className="stage-index">03 / 10</span></div>
    {flags.length > 0 && <FlagList flags={flags} />}
    <div className="scope-grid"><section className="panel"><div className="panel-heading"><div><p className="eyebrow">Deliverables</p><h2>What the engagement produces</h2></div></div><div className="scope-list">{scope.deliverables.map((item: any) => <article className="scope-item" key={item.id}><div><strong>{item.name}</strong><p>{item.description}</p></div>{item.optional && <span className="optional-label">Optional</span>}</article>)}</div></section>
      <div className="scope-side"><section className="panel"><p className="eyebrow">Milestones</p><h2>Sequence to launch</h2><ol className="milestone-list">{scope.milestones.map((item: any) => <li key={item.id}><span>{item.sequence}</span><div><strong>{item.name}</strong><p>{item.targetDescription}</p></div></li>)}</ol></section>
      <section className="panel"><p className="eyebrow">Questions to resolve</p><h2>Keep assumptions honest.</h2>{question && !resolved ? <div className="question-card"><span className="question-label">Open question</span><p>Can the legacy CMS expose the product metadata needed by the new site?</p>{!showResolver ? <Button type="button" tone="secondary" data-testid="resolve-open-question" onClick={() => setShowResolver(true)}>Resolve</Button> : <div className="resolver"><label className="field"><span className="field-label">Resolution</span><textarea aria-label="Resolution" value={resolution} onChange={(event) => setResolution(event.target.value)} /></label><div className="button-row"><Button type="button" tone="secondary" onClick={() => setShowResolver(false)}>Cancel</Button><Button type="button" onClick={resolveQuestion}>Confirm</Button></div></div>}</div> : <p className="empty-state">Scope is ready for the next gate.</p>}</section></div>
    </div>
    <div className="scope-bottom"><section className="panel"><p className="eyebrow">Assumptions</p><div className="tag-list">{scope.assumptions.map((item: any) => <span key={item.id ?? item}>{item.text ?? item}</span>)}</div></section><section className="panel"><p className="eyebrow">Exclusions</p><div className="tag-list tag-list-muted">{scope.exclusions.map((item: string) => <span key={item}>{item}</span>)}</div></section></div>
  </div></AppShell>;
}
