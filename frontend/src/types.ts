export interface StoreStats {
  documents: number;
  chunks: number;
  dim: number;
}

export interface Health {
  status: string;
  store: StoreStats;
  ollama_ready: boolean;
}

export interface Config {
  embed_backend: string;
  llm_backend: string;
  ollama_host: string;
  embed_model: string;
  chat_model: string;
  chunk_tokens: number;
  chunk_overlap: number;
  top_k: number;
  candidate_k: number;
  min_score: number;
}

export interface DocInfo {
  id: number;
  title: string;
  source: string;
  n_chunks: number;
  created: number;
}

export interface Retrieved {
  chunk_id: number;
  doc_id: number;
  doc_title: string;
  index: number;
  text: string;
  score: number;
  dense: number | null;
  lexical: number | null;
}

export interface SearchResponse {
  results: Retrieved[];
  best_dense: number;
  min_score: number;
}

export interface EvalSummary {
  n_questions: number;
  hit_at_k: number;
  mrr: number;
  answer_coverage: number;
  grounded_rate: number;
  accuracy: number;
  hybrid: boolean;
  top_k: number;
}

export interface EvalQuestion {
  question: string;
  answerable: boolean;
  hit: boolean;
  reciprocal_rank: number;
  best_dense: number;
  refused: boolean;
  grounded: boolean;
  coverage: number;
  correct: boolean;
  answer: string;
}

export interface EvalResult {
  summary: EvalSummary | null;
  per_question: EvalQuestion[];
}
