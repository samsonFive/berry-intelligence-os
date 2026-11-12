/** Existing read-only Learn API models; educational status is not evidence trust. */
export type LearningKind = 'concept' | 'lesson';
export type KnownKnowledgeClass = 'foundational_knowledge' | 'regional_production_practice'
  | 'current_technical_guidance' | 'consumer_sensory_observations';
export interface EducationBoundary { label: string; competitive_evidence: false; note: string }
export interface LearningSelection {
  q: string; pillar: string; knowledge_class: string; kind: 'all' | LearningKind; offset: number; limit: number;
}
export interface LearningItem {
  kind: LearningKind; id: string; title: string; slug?: string; summary?: string;
  pillar: string; pillar_label: string; knowledge_class: string; knowledge_class_label: string;
  education_status: string; status_label: string; partial: boolean;
  reviewed_at: string; review_by: string; is_stale: boolean; needs_review_cadence: boolean;
  source_count: number; media_count: number; revision?: number; updated_at?: string;
  scope: { berry_id: string; berry_label: string; geography_id: string; geography_label: string; berry_ids: string[] };
  href: string; expand_href: string;
}
export interface LearningCollection {
  status: 'available' | 'empty' | 'unavailable'; total: number | null; matched_count: number | null;
  items: LearningItem[]; has_more: boolean;
}
export interface LearningCatalog {
  education_boundary: EducationBoundary;
  collections: { concepts: LearningCollection; lessons: LearningCollection };
  counts: { concepts: number | null; lessons: number | null; stale: number | null; partial: number | null };
  facets: { pillars: { id: string; label: string; count: number | null }[]; knowledge_classes: { id: string; label: string; count: number | null }[] };
  selection: LearningSelection;
}
export interface LearningResource {
  title?: string; publisher?: string; url?: string; reference_ids?: string[];
  kind?: string; image_url?: string; source_page?: string; caption?: string;
  alt?: string; license?: string; license_url?: string; attribution?: string;
  reuse_basis?: string; attribution_required?: boolean; verified_at?: string;
  display?: 'source_link';
}
export interface TeachingDiagramModel {
  title: string; intro: string; limit: string; checked_on?: string;
  mode?: string; illustration?: string; illustrative?: boolean; attribution?: string;
  sources: LearningResource[];
  steps: { title: string; icon: string; caption: string; detail: string }[];
}
export interface TeachingModel {
  figure?: LearningResource | null; diagram?: TeachingDiagramModel | null;
  cane_diagram?: boolean; legacy_visual_href?: string;
  companion?: { id: string; title: string; href: string }; note?: string;
}
export interface LearningSection { id: string; title: string; text: string }
export interface LearningContent {
  item: LearningItem; education_boundary: EducationBoundary; sections: LearningSection[];
  citations: LearningResource[]; media: LearningResource[]; teaching?: TeachingModel | null;
  berry_notes: { berry_id: string; berry_label: string; note: string }[];
  related: { kind: 'concept'; id: string; title: string; href: string }[];
  content_markdown?: string; expand_href: string;
  clarification?: { retained_original: { summary: string; what_is_it: string } };
  provenance: { education_boundary: EducationBoundary; knowledge_class_note?: string;
    job_id?: string; revision?: number; created_at?: string; updated_at?: string; history_count?: number };
}
