/**
 * Upload page — prototype screen 01 (Empty / Upload).
 *
 * Editorial hero on the left, drop zone + recent reviews on the right.
 * The drop zone is fully keyboard-accessible (NFR-005): role="button",
 * tabIndex=0, aria-label, and Enter/Space open the file picker.
 *
 * On a successful upload the page navigates to `/processing/{docId}`,
 * passing the filename + page count via router state so the Processing
 * screen can render the doc-pill without an extra fetch.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppContext } from '../App';
import { ApiError } from '../api/client';
import {
  type DocumentSummary,
  listDocuments,
  uploadDocument,
} from '../api/documents';

/** Tiny relative-time helper. Local-only — no Intl.RelativeTimeFormat hop. */
function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const diff = Date.now() - then;
  if (diff < 0) return 'just now';
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'yesterday';
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}

function isPdf(file: File): boolean {
  if (file.type === 'application/pdf') return true;
  return file.name.toLowerCase().endsWith('.pdf');
}

export function Upload(): JSX.Element {
  const navigate = useNavigate();
  const { setActiveDoc, setStatus } = useAppContext();
  const inputRef = useRef<HTMLInputElement | null>(null);

  const [recent, setRecent] = useState<DocumentSummary[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset chrome when this page mounts — we're at the top of the funnel.
  useEffect(() => {
    setActiveDoc(null);
    setStatus('idle');
  }, [setActiveDoc, setStatus]);

  // Recent reviews — silent failure (the empty state covers backend-down).
  useEffect(() => {
    let cancelled = false;
    listDocuments()
      .then((rows) => {
        if (cancelled) return;
        setRecent(rows.slice(0, 5));
      })
      .catch(() => {
        if (cancelled) return;
        setRecent([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      if (!isPdf(file)) {
        setError('Only PDF files are accepted (.pdf)');
        return;
      }
      setIsUploading(true);
      setStatus('working');
      try {
        const uploaded = await uploadDocument(file);
        navigate(`/processing/${uploaded.document_id}`, {
          state: {
            filename: uploaded.filename,
            pageCount: uploaded.page_count,
          },
        });
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : 'Upload failed';
        setError(message);
        setIsUploading(false);
        setStatus('idle');
      }
    },
    [navigate, setStatus],
  );

  const onPickClick = useCallback(() => {
    if (isUploading) return;
    inputRef.current?.click();
  }, [isUploading]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (isUploading) return;
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        inputRef.current?.click();
      }
    },
    [isUploading],
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        void handleFile(file);
      }
      // Reset so picking the same file twice still triggers onChange.
      e.target.value = '';
    },
    [handleFile],
  );

  const onDragEnter = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      if (isUploading) return;
      setIsDragging(true);
    },
    [isUploading],
  );
  const onDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  }, []);
  const onDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);
  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      if (isUploading) return;
      const file = e.dataTransfer.files?.[0];
      if (file) {
        void handleFile(file);
      }
    },
    [handleFile, isUploading],
  );

  const dropZoneClass = [
    'border-[1.5px] border-dashed rounded-md p-12 text-center cursor-pointer transition-all',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-burgundy focus-visible:ring-offset-2',
    isDragging
      ? 'border-burgundy bg-burgundy-soft'
      : 'border-line bg-bg-soft hover:border-burgundy hover:bg-burgundy-soft',
    isUploading ? 'opacity-60 cursor-not-allowed' : '',
  ].join(' ');

  return (
    <div className="flex-1 flex items-center justify-center px-8 py-12 overflow-y-auto">
      <div className="max-w-[1100px] w-full grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-16 items-center">
        {/* Hero left */}
        <div className="lg:pr-5">
          <div className="font-mono text-[10px] text-burgundy uppercase tracking-[0.18em] mb-4 flex items-center gap-3 before:content-[''] before:w-7 before:h-px before:bg-burgundy">
            A new instrument · for old standards
          </div>
          <h1 className="font-serif text-6xl font-semibold leading-none tracking-[-0.03em] mb-5">
            Read the contract.
            <br />
            <em className="italic font-normal text-burgundy">
              Keep the secret.
            </em>
          </h1>
          <p className="text-[17px] text-ink-soft leading-relaxed mb-8 max-w-[480px]">
            Drop a contract. Get a risk analysis, a redline pack, and a
            plain-English summary you can send to your client &mdash; all
            generated <strong className="font-semibold text-ink">on this machine</strong>,
            by a model that runs locally and never sees the network.
          </p>
          <div className="flex gap-8 pt-6 border-t border-line font-mono text-[11px] uppercase tracking-[0.10em] text-ink-muted">
            <div>
              <b className="block mb-0.5 font-serif italic font-semibold text-base text-ink normal-case tracking-normal">
                0
              </b>
              requests sent
            </div>
            <div>
              <b className="block mb-0.5 font-serif italic font-semibold text-base text-ink normal-case tracking-normal">
                ~45s
              </b>
              avg. analysis
            </div>
            <div>
              <b className="block mb-0.5 font-serif italic font-semibold text-base text-ink normal-case tracking-normal">
                128K
              </b>
              context window
            </div>
          </div>
        </div>

        {/* Upload right */}
        <div className="bg-bg border border-line rounded-lg p-7 shadow-[0_20px_50px_-30px_rgba(0,0,0,0.15)]">
          <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-ink-muted mb-4">
            Begin a review
          </div>

          {error ? (
            <div
              role="alert"
              data-testid="upload-error"
              className="bg-danger-soft border border-danger text-danger rounded-md p-3 mb-4 text-sm"
            >
              {error}
            </div>
          ) : null}

          <div
            role="button"
            tabIndex={isUploading ? -1 : 0}
            aria-label="Drop a PDF or press Enter to choose a file"
            aria-disabled={isUploading}
            data-dragging={isDragging || undefined}
            data-testid="upload-zone"
            className={dropZoneClass}
            onClick={onPickClick}
            onKeyDown={onKeyDown}
            onDragEnter={onDragEnter}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
          >
            <div className="font-serif text-[56px] italic font-light text-burgundy leading-none mb-3">
              ↓
            </div>
            <div className="text-[15px] font-medium text-ink mb-1.5">
              {isUploading ? 'Uploading…' : 'Drop PDFs here'}
            </div>
            <div className="font-mono text-[10px] text-ink-muted uppercase tracking-[0.12em]">
              or click · up to 5 documents
            </div>
          </div>

          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={onInputChange}
            data-testid="upload-input"
          />

          <div className="mt-6 pt-5 border-t border-line-soft">
            <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-ink-muted mb-2.5">
              Recent reviews
            </div>
            {recent.length === 0 ? (
              <p
                className="text-[13px] text-ink-muted italic"
                data-testid="recent-empty"
              >
                Drop your first contract above
              </p>
            ) : (
              <ul data-testid="recent-list" className="space-y-0">
                {recent.map((doc) => (
                  <li
                    key={doc.id}
                    className="flex justify-between items-center py-2 border-b border-line-soft last:border-b-0"
                  >
                    <span className="text-[13px] font-medium text-ink hover:text-burgundy transition-colors truncate">
                      {doc.filename}
                    </span>
                    <span className="font-mono text-[10px] text-ink-muted shrink-0 ml-3">
                      {relativeTime(doc.created_at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Upload;
