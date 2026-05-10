/**
 * Upload page tests — Sprint 2 / US1.
 *
 * Covers: hero copy, drop-zone visual cue + keyboard reachability, recent
 * reviews list (populated and empty), non-PDF rejection, successful upload
 * navigation, and verbatim backend error surfacing.
 *
 * The page calls useNavigate(); we mock react-router-dom to capture it
 * and we wrap <Upload /> in MemoryRouter so other hooks resolve.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const navigateMock = vi.fn();

vi.mock('react-router-dom', async (importOriginal) => {
  const mod =
    await importOriginal<typeof import('react-router-dom')>();
  return {
    ...mod,
    useNavigate: () => navigateMock,
  };
});

// Mock the API surface BEFORE importing the page (vi.mock is hoisted).
vi.mock('../api/documents', () => ({
  listDocuments: vi.fn(),
  uploadDocument: vi.fn(),
}));

import { Upload } from './Upload';
import { ApiError } from '../api/client';
import { listDocuments, uploadDocument } from '../api/documents';

// Provide a no-op outlet context so useAppContext() doesn't throw.
function renderUpload(): void {
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route
          element={
            <OutletShell />
          }
        >
          <Route path="/" element={<Upload />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

import { Outlet } from 'react-router-dom';
function OutletShell(): JSX.Element {
  const ctx = {
    setActiveDoc: () => undefined,
    setStatus: () => undefined,
  };
  return <Outlet context={ctx} />;
}

describe('<Upload />', () => {
  beforeEach(() => {
    navigateMock.mockReset();
    vi.mocked(listDocuments).mockReset();
    vi.mocked(uploadDocument).mockReset();
    vi.mocked(listDocuments).mockResolvedValue([]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders the hero copy verbatim', async () => {
    renderUpload();
    expect(screen.getByText(/Read the contract\./i)).toBeInTheDocument();
    expect(screen.getByText(/Keep the secret\./i)).toBeInTheDocument();
    expect(
      screen.getByText(/on this machine/i),
    ).toBeInTheDocument();
    // drain
    await screen.findByTestId('recent-empty');
  });

  it('renders the drop zone with visual cue and is keyboard-reachable', async () => {
    renderUpload();
    const zone = screen.getByTestId('upload-zone');
    expect(zone).toHaveAttribute('role', 'button');
    expect(zone).toHaveAttribute('tabIndex', '0');
    expect(screen.getByText(/Drop PDFs here/i)).toBeInTheDocument();
    expect(
      screen.getByText(/or click · up to 5 documents/i),
    ).toBeInTheDocument();
    await screen.findByTestId('recent-empty');
  });

  it('populates the recent reviews list from listDocuments()', async () => {
    vi.mocked(listDocuments).mockResolvedValue([
      {
        id: 'doc-a',
        filename: 'acme-msa.pdf',
        contract_type: 'MSA',
        page_count: 8,
        created_at: new Date(Date.now() - 5 * 60_000).toISOString(),
      },
      {
        id: 'doc-b',
        filename: 'nda-v3.pdf',
        contract_type: 'NDA',
        page_count: 4,
        created_at: new Date(Date.now() - 2 * 3600_000).toISOString(),
      },
    ]);
    renderUpload();
    await screen.findByText('acme-msa.pdf');
    expect(screen.getByText('nda-v3.pdf')).toBeInTheDocument();
    expect(screen.getByText(/5m ago/)).toBeInTheDocument();
    expect(screen.getByText(/2h ago/)).toBeInTheDocument();
  });

  it('shows the empty state when there are no recent reviews', async () => {
    vi.mocked(listDocuments).mockResolvedValue([]);
    renderUpload();
    expect(
      await screen.findByTestId('recent-empty'),
    ).toHaveTextContent(/Drop your first contract above/i);
  });

  it('rejects non-PDF files with an error mentioning PDF', async () => {
    renderUpload();
    // The file <input> uses accept="application/pdf", so userEvent.upload
    // silently drops a .txt file (it enforces accept). A user can still
    // bypass that filter by drag-and-drop, so simulate the same path here.
    const zone = screen.getByTestId('upload-zone');
    const txtFile = new File(['hello'], 'notes.txt', { type: 'text/plain' });
    fireEvent.drop(zone, { dataTransfer: { files: [txtFile] } });
    const err = await screen.findByTestId('upload-error');
    expect(err).toHaveTextContent(/PDF/i);
    // Did NOT attempt the upload.
    expect(uploadDocument).not.toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it('uploads a PDF and navigates to /processing/{docId}', async () => {
    vi.mocked(uploadDocument).mockResolvedValue({
      document_id: 'doc-xyz',
      filename: 'acme-msa.pdf',
      page_count: 8,
      contract_type: 'MSA',
    });
    renderUpload();
    const input = screen.getByTestId('upload-input') as HTMLInputElement;
    const pdf = new File(
      [new Uint8Array([0x25, 0x50, 0x44, 0x46])],
      'acme-msa.pdf',
      { type: 'application/pdf' },
    );

    await userEvent.upload(input, pdf);

    await waitFor(() => {
      expect(uploadDocument).toHaveBeenCalledTimes(1);
    });
    expect(uploadDocument).toHaveBeenCalledWith(pdf);

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith('/processing/doc-xyz', {
        state: { filename: 'acme-msa.pdf', pageCount: 8 },
      });
    });
  });

  it('surfaces the verbatim backend error (ApiError.message) above the drop zone', async () => {
    vi.mocked(uploadDocument).mockRejectedValue(
      new ApiError('Only PDF files are accepted', 415),
    );
    renderUpload();
    const input = screen.getByTestId('upload-input') as HTMLInputElement;
    const pdf = new File(
      [new Uint8Array([0x25, 0x50, 0x44, 0x46])],
      'mystery.pdf',
      { type: 'application/pdf' },
    );

    await userEvent.upload(input, pdf);

    const err = await screen.findByTestId('upload-error');
    expect(err).toHaveTextContent('Only PDF files are accepted');
    // Backend error → no navigation.
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it('uploads when a file is dropped onto the zone', async () => {
    vi.mocked(uploadDocument).mockResolvedValue({
      document_id: 'doc-drop',
      filename: 'dropped.pdf',
      page_count: 2,
      contract_type: null,
    });
    renderUpload();
    const zone = screen.getByTestId('upload-zone');
    const pdf = new File(
      [new Uint8Array([0x25, 0x50, 0x44, 0x46])],
      'dropped.pdf',
      { type: 'application/pdf' },
    );

    fireEvent.drop(zone, { dataTransfer: { files: [pdf] } });

    await waitFor(() => {
      expect(uploadDocument).toHaveBeenCalledWith(pdf);
    });
    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith('/processing/doc-drop', {
        state: { filename: 'dropped.pdf', pageCount: 2 },
      });
    });
  });
});
