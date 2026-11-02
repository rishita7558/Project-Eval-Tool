import React, { useState } from 'react';
import { CheckCircle2, AlertTriangle, XCircle, ShieldCheck, Cpu, Search, Activity, UserCheck } from 'lucide-react';

export default function AgenticTelemetryInspector({ result, onClose, onSaveOverride }) {
  if (!result) return null;

  const agentic = result.agenticExecution || {};
  const specialists = agentic.specialistAgents || {};
  const auditor = specialists.evidenceAuditor || null;
  const critic = specialists.criticReviewer || null;
  const breakdown = result.scoreBreakdown || {};

  const [overrideScore, setOverrideScore] = useState(result.overallScore ?? result.score ?? '');
  const [overrideNotes, setOverrideNotes] = useState('');
  const [isOverriding, setIsOverriding] = useState(false);

  const modeLabels = {
    0: 'Mode 0 — Baseline (Standard)',
    1: 'Mode 1 — Assisted (Structured Plan)',
    2: 'Mode 2 — Bounded Autonomous (Adaptive Tools)',
    3: 'Mode 3 — Multi-Agent Review (Specialists)',
  };

  const modeName = modeLabels[agentic.mode] || (result.agenticExecution ? `Mode ${agentic.mode}` : 'Baseline Execution');

  const defaultPlanSteps = [
    { tool: 'validate_rubric', purpose: 'Validate grading bounds & establish integrity snapshot', status: 'UNAVAILABLE' },
    { tool: 'validate_submission_input', purpose: 'Scan text & protect against prompt injection', status: 'UNAVAILABLE' },
    { tool: 'evaluate_against_rubric', purpose: 'Evaluate criterion performance with Groq/Ollama', status: 'UNAVAILABLE' },
    { tool: 'verify_evidence_spans', purpose: 'Independently audit quoted text against submission', status: 'UNAVAILABLE' },
    { tool: 'calculate_final_score', purpose: 'Deterministically sum scores & clamp to bounds', status: 'UNAVAILABLE' },
    { tool: 'run_quality_checks', purpose: 'Enforce state machine review policy', status: 'UNAVAILABLE' },
  ];
  const planSteps = Array.isArray(agentic.planSteps) && agentic.planSteps.length > 0
    ? agentic.planSteps
    : defaultPlanSteps;
  const hasValidScore = typeof result.overallScore === 'number' && Number.isFinite(result.overallScore);
  const status = result.evaluationStatus || (result.needsReview ? 'NEEDS_REVIEW' : hasValidScore ? 'COMPLETED' : 'FAILED');
  const evidenceRate = agentic.evidenceVerificationRate;

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(3, 7, 18, 0.8)',
      backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 9999, padding: '1.5rem',
    }}>
      <div style={{
        background: '#0f172a',
        border: '1px solid rgba(99, 102, 241, 0.3)',
        borderRadius: 18,
        width: '100%', maxWidth: 860,
        maxHeight: '90vh',
        overflowY: 'auto',
        color: '#f8fafc',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
        padding: '1.75rem',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid #334155', paddingBottom: '1rem', marginBottom: '1.25rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <h3 style={{ margin: 0, fontSize: '1.3rem', color: '#e2e8f0', fontWeight: 700 }}>
                🔍 Agentic Audit & Evidence Inspector
              </h3>
              <span style={{
                background: 'rgba(99, 102, 241, 0.2)',
                border: '1px solid rgba(99, 102, 241, 0.4)',
                color: '#a5b4fc',
                borderRadius: 20, padding: '2px 10px', fontSize: '0.75rem', fontWeight: 600,
              }}>
                {modeName}
              </span>
            </div>
            <p style={{ margin: '4px 0 0', color: '#94a3b8', fontSize: '0.85rem' }}>
              Student: <strong>{result.studentName || 'Unknown'}</strong> ({result.rollNumber || 'N/A'}) · File: <code>{result.fileName || result.file_name || 'submission.txt'}</code>
            </p>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: '1.5rem', cursor: 'pointer', padding: '0 0.5rem' }}
          >
            ✕
          </button>
        </div>

        {/* Status & Telemetry Bar */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem', marginBottom: '1.5rem' }}>
          <div style={{ background: 'rgba(30, 41, 59, 0.7)', padding: '0.75rem', borderRadius: 10, border: '1px solid #334155' }}>
            <span style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5 }}>Final Score</span>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#38bdf8' }}>
              {hasValidScore ? result.overallScore : '—'} / {result.maxScore ?? 100}
              <span style={{ fontSize: '0.8rem', color: '#94a3b8', marginLeft: 6 }}>({result.gradeLabel || '—'})</span>
            </div>
          </div>

          <div style={{ background: 'rgba(30, 41, 59, 0.7)', padding: '0.75rem', borderRadius: 10, border: '1px solid #334155' }}>
            <span style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5 }}>Review Status</span>
            <div style={{ fontSize: '1rem', fontWeight: 600, marginTop: 3 }}>
              {status === 'NEEDS_REVIEW' ? (
                <span style={{ color: '#fb923c', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <AlertTriangle size={16} /> Needs Review
                </span>
              ) : status === 'COMPLETED' && hasValidScore ? (
                <span style={{ color: '#4ade80', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <CheckCircle2 size={16} /> Completed
                </span>
              ) : (
                <span style={{ color: '#f87171', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <XCircle size={16} /> Failed
                </span>
              )}
            </div>
          </div>

          <div style={{ background: 'rgba(30, 41, 59, 0.7)', padding: '0.75rem', borderRadius: 10, border: '1px solid #334155' }}>
            <span style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5 }}>Evidence Grounding</span>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#4ade80' }}>
              {typeof evidenceRate === 'number'
                ? `${(evidenceRate * 100).toFixed(0)}%`
                : 'Unavailable'}
            </div>
          </div>

          <div style={{ background: 'rgba(30, 41, 59, 0.7)', padding: '0.75rem', borderRadius: 10, border: '1px solid #334155' }}>
            <span style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5 }}>Execution Latency</span>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#c084fc' }}>
              {agentic.elapsedSeconds ? `${agentic.elapsedSeconds}s` : '< 1.5s'}
            </div>
          </div>
        </div>

        {/* Review Flags Alert if any */}
        {result.reviewFlags && result.reviewFlags.length > 0 && (
          <div style={{ background: 'rgba(251, 146, 60, 0.1)', border: '1px solid rgba(251, 146, 60, 0.3)', borderRadius: 10, padding: '0.75rem 1rem', marginBottom: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#fb923c', fontWeight: 600, fontSize: '0.85rem' }}>
              <AlertTriangle size={16} /> Automated Review Flags Detected:
            </div>
            <ul style={{ margin: '4px 0 0', paddingLeft: '1.25rem', color: '#fdba74', fontSize: '0.8rem' }}>
              {result.reviewFlags.map((flag, idx) => (
                <li key={idx}>{flag}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Section 1: Execution Plan & Bounded Tools */}
        <div style={{ marginBottom: '1.5rem' }}>
          <h4 style={{ margin: '0 0 0.6rem', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Cpu size={16} color="#818cf8" /> Validated Execution Plan Steps
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
            {planSteps.map((step, idx) => (
              <div key={idx} style={{
                background: 'rgba(15, 23, 42, 0.8)',
                border: '1px solid rgba(51, 65, 85, 0.8)',
                borderRadius: 8, padding: '0.6rem 0.75rem',
                fontSize: '0.78rem',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                  <code style={{ color: '#38bdf8', fontWeight: 600 }}>{step.tool}</code>
                  <span style={{ color: step.status === 'FAILED' ? '#f87171' : step.status === 'COMPLETED' ? '#4ade80' : '#fbbf24', fontSize: '0.7rem' }}>
                    {step.status === 'FAILED' ? '✕' : step.status === 'COMPLETED' ? '✓' : '—'}
                  </span>
                </div>
                <div style={{ color: '#94a3b8', fontSize: '0.72rem' }}>{step.purpose}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Section 2: Specialist Agent Findings (Multi-Agent Mode) */}
        {(auditor || critic) && (
          <div style={{ marginBottom: '1.5rem' }}>
            <h4 style={{ margin: '0 0 0.6rem', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
              <ShieldCheck size={16} color="#34d399" /> Specialist Multi-Agent Collaboration
            </h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              {/* Evidence Auditor */}
              {auditor && (
                <div style={{ background: 'rgba(15, 23, 42, 0.9)', border: '1px solid #334155', borderRadius: 10, padding: '0.85rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontWeight: 600, color: '#38bdf8', fontSize: '0.85rem' }}>Evidence Auditor</span>
                    <span style={{
                      borderRadius: 12, padding: '1px 8px', fontSize: '0.7rem', fontWeight: 600,
                      background: auditor.decision === 'CONTINUE' ? 'rgba(74, 222, 128, 0.15)' : 'rgba(251, 146, 60, 0.15)',
                      color: auditor.decision === 'CONTINUE' ? '#4ade80' : '#fb923c',
                    }}>
                      {auditor.decision}
                    </span>
                  </div>
                  <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.78rem' }}>{auditor.rationale}</p>
                </div>
              )}

              {/* Critic Reviewer */}
              {critic && (
                <div style={{ background: 'rgba(15, 23, 42, 0.9)', border: '1px solid #334155', borderRadius: 10, padding: '0.85rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontWeight: 600, color: '#c084fc', fontSize: '0.85rem' }}>Critic / Consistency Reviewer</span>
                    <span style={{
                      borderRadius: 12, padding: '1px 8px', fontSize: '0.7rem', fontWeight: 600,
                      background: critic.decision === 'CONTINUE' ? 'rgba(74, 222, 128, 0.15)' : 'rgba(251, 146, 60, 0.15)',
                      color: critic.decision === 'CONTINUE' ? '#4ade80' : '#fb923c',
                    }}>
                      {critic.decision}
                    </span>
                  </div>
                  <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.78rem' }}>{critic.rationale}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Section 3: Evidence Citation Inspector */}
        <div style={{ marginBottom: '1.5rem' }}>
          <h4 style={{ margin: '0 0 0.6rem', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Search size={16} color="#38bdf8" /> Rubric Criteria & Grounded Evidence Citations
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {Object.entries(breakdown).map(([critName, critData]) => (
              <div key={critName} style={{
                background: 'rgba(15, 23, 42, 0.7)',
                border: '1px solid #334155',
                borderRadius: 8, padding: '0.75rem',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, color: '#e2e8f0', fontSize: '0.85rem' }}>{critName}</span>
                  <span style={{ fontWeight: 700, color: '#38bdf8', fontSize: '0.85rem' }}>
                    {critData.score} / {critData.maxScore}
                  </span>
                </div>
                <div style={{ color: '#94a3b8', fontSize: '0.78rem', marginBottom: 4 }}>
                  <strong>Rationale:</strong> {critData.reason || critData.feedback || '—'}
                </div>
                {critData.evidence ? (
                  <div style={{ background: 'rgba(30, 41, 59, 0.5)', padding: '0.4rem 0.6rem', borderRadius: 6, fontSize: '0.75rem', color: '#cbd5e1' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: critData.evidenceVerified ? '#4ade80' : '#fb923c', marginBottom: 2, fontWeight: 600 }}>
                      <CheckCircle2 size={12} /> {critData.evidenceVerified ? 'Verified Student Text Quotation:' : 'Cited Student Text Quotation:'}
                    </div>
                    <em>"{critData.evidence}"</em>
                  </div>
                ) : (
                  <div style={{ color: '#fbbf24', fontSize: '0.75rem' }}>No evidence citation was provided.</div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Section 4: Human-in-the-Loop Professor Override Protection */}
        <div style={{
          background: 'rgba(30, 41, 59, 0.4)',
          border: '1px solid rgba(99, 102, 241, 0.25)',
          borderRadius: 12, padding: '1rem',
        }}>
          <h4 style={{ margin: '0 0 0.6rem', color: '#e2e8f0', fontSize: '0.9rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <UserCheck size={16} color="#818cf8" /> Professor Override & Approval Action
          </h4>
          <p style={{ margin: '0 0 0.75rem', color: '#94a3b8', fontSize: '0.78rem' }}>
            Agents recommend evaluations, but professors retain final grading authority. You can approve this result or submit an explicit manual grade override.
          </p>

          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <input
              type="number"
              value={overrideScore}
              onChange={(e) => setOverrideScore(e.target.value)}
              step="0.5"
              min="0"
              max={result.maxScore || 100}
              style={{
                background: '#1e293b', border: '1px solid #475569', borderRadius: 8,
                color: '#f8fafc', padding: '0.4rem 0.6rem', width: 100, fontSize: '0.85rem',
              }}
            />
            <input
              type="text"
              placeholder="Professor review notes (optional)…"
              value={overrideNotes}
              onChange={(e) => setOverrideNotes(e.target.value)}
              style={{
                flex: 1, background: '#1e293b', border: '1px solid #475569', borderRadius: 8,
                color: '#f8fafc', padding: '0.4rem 0.6rem', fontSize: '0.85rem',
              }}
            />
            <button
              disabled={overrideScore === '' || !Number.isFinite(Number(overrideScore))}
              onClick={() => {
                if (onSaveOverride) {
                  onSaveOverride(result, overrideScore, overrideNotes);
                }
                onClose();
              }}
              style={{
                background: '#4f46e5', border: 'none', borderRadius: 8,
                color: '#fff', padding: '0.45rem 1rem', fontSize: '0.82rem', fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Approve / Save Override
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
