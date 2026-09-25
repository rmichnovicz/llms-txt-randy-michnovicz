import { ArrowUp } from "lucide-react";
import type { Project, Question } from "./api";

export default function QuestionCard({
  question,
  sources,
  blocked,
  answer,
  setAnswer,
  onAnswer,
  onDismiss,
}: {
  question: Question;
  sources: NonNullable<Project["snapshot"]>["sources"];
  blocked: boolean;
  answer: string;
  setAnswer: (s: string) => void;
  onAnswer: (s: string) => void;
  onDismiss: () => void;
}) {
  return (
    <section className="question-card">
      <span className="question-label">A question for you</span>
      <h2>{question.data.question}</h2>
      <p>{question.data.rationale}</p>
      <div className="options">
        {question.data.options.map((option, index) => (
          <button
            key={option}
            disabled={blocked}
            onClick={() => onAnswer(option)}
          >
            <span>{option}</span>
            {question.data.recommended_option === index && (
              <small>Recommended</small>
            )}
          </button>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onAnswer(answer.trim());
        }}
      >
        <label htmlFor="answer">Or answer in your own words</label>
        <div className="answer-entry">
          <textarea
            rows={2}
            id="answer"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            maxLength={2500}
            placeholder="Here’s what I have in mind…"
          />
          <button aria-label="Save answer" disabled={blocked || !answer.trim()}>
            <ArrowUp size={16} />
          </button>
        </div>
      </form>
      <div className="question-footer">
        <details>
          <summary>Why this came up</summary>
          {question.data.evidence_ids.map((id) => {
            const s = sources.find((s) => s.id === id);
            return s ? (
              <a key={id} href={s.url} target="_blank" rel="noreferrer">
                {s.title}
              </a>
            ) : (
              <span key={id}>Your saved direction</span>
            );
          })}
        </details>
        <button disabled={blocked} onClick={onDismiss}>
          Dismiss
        </button>
      </div>
    </section>
  );
}
