import { useEffect, useRef, useState } from 'react';
import { getPostes, uploadCV } from '../api/api';

export default function CVUpload({ onUploadSuccess }) {
  const inputRef = useRef(null);
  const [jobs, setJobs] = useState([]);
  const [file, setFile] = useState(null);
  const [sourceEmail, setSourceEmail] = useState('');
  const [targetJobId, setTargetJobId] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [uploadedCandidate, setUploadedCandidate] = useState(null);

  useEffect(() => {
    getPostes().then((res) => setJobs(res.data || [])).catch(() => {});
  }, []);

  const pickFile = (selected) => {
    if (!selected) return;
    const lower = selected.name.toLowerCase();
    if (!lower.endsWith('.pdf') && !lower.endsWith('.docx')) {
      setError('Selectionnez un CV au format PDF ou DOCX.');
      setFile(null);
      return;
    }
    setFile(selected);
    setError('');
    setSuccess('');
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!file) {
      setError('Aucun CV selectionne.');
      return;
    }

    setUploading(true);
    setError('');
    setSuccess('');

    try {
      const formData = new FormData();
      formData.append('cv', file);
      formData.append('source', 'manual');
      if (sourceEmail) formData.append('sourceEmail', sourceEmail);
      if (targetJobId) formData.append('targetJobId', targetJobId);

      const res = await uploadCV(formData);
      setUploadedCandidate(res.data.candidate);
      setSuccess(`CV integre pour ${res.data.candidate.fullName}.`);
      setFile(null);
      setSourceEmail('');
      setTargetJobId('');
      if (inputRef.current) inputRef.current.value = '';
      if (onUploadSuccess) onUploadSuccess();
    } catch (err) {
      setError(err?.response?.data?.error || 'Echec de l import du CV.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-header">
        <span className="card-title">Import manuel d un CV</span>
      </div>
      <div className="card-body">
        <form onSubmit={handleSubmit} className="upload-grid">
          <label
            className="upload-dropzone"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              pickFile(event.dataTransfer.files?.[0]);
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx"
              onChange={(event) => pickFile(event.target.files?.[0])}
              style={{ display: 'none' }}
            />
            <div className="upload-icon">{file ? 'CV' : '+'}</div>
            <div className="upload-title">{file ? file.name : 'Glisser ou choisir un CV'}</div>
            <div className="upload-subtitle">
              {file ? `${(file.size / 1024).toFixed(0)} Ko` : 'PDF ou DOCX, traite et score automatiquement'}
            </div>
          </label>

          <div style={{ display: 'grid', gap: 12 }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Email source</label>
              <input
                className="form-input"
                type="email"
                value={sourceEmail}
                placeholder="candidat@example.com"
                onChange={(event) => setSourceEmail(event.target.value)}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Poste cible</label>
              <select className="form-select" value={targetJobId} onChange={(event) => setTargetJobId(event.target.value)}>
                <option value="">Classification automatique</option>
                {jobs.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.titre}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button className="btn btn-primary" type="submit" disabled={uploading || !file}>
                {uploading ? 'Import en cours...' : 'Importer et scorer'}
              </button>
              <button
                className="btn btn-ghost"
                type="button"
                onClick={() => {
                  setFile(null);
                  setError('');
                  setSuccess('');
                  if (inputRef.current) inputRef.current.value = '';
                }}
              >
                Reinitialiser
              </button>
            </div>
          </div>
        </form>

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}
        {success && <div className="alert alert-success" style={{ marginTop: 16 }}>{success}</div>}

        {uploadedCandidate && (
          <div className="candidate-inline-summary">
            <div>
              <div className="candidate-inline-name">{uploadedCandidate.fullName}</div>
              <div className="candidate-inline-meta">
                {uploadedCandidate.targetJob || 'Poste auto'} • {uploadedCandidate.recommendation}
              </div>
            </div>
            <div className="candidate-inline-score">{uploadedCandidate.matchScore?.toFixed(1)}%</div>
          </div>
        )}
      </div>
    </div>
  );
}
