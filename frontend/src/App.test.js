import { render, screen } from '@testing-library/react';
import App from './App';

test('renders recruitment dashboard heading', () => {
  global.fetch = jest.fn((url) => {
    if (String(url).includes('/api/candidates/1/')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          candidate: {
            id: 1,
            fullName: 'Salma Bennani',
            matchScore: 91.5,
            profileLabel: 'Data Analyst',
            targetJob: 'Data Analyst',
            educationLevel: 'Master',
            yearsExperience: 3,
            source: 'email',
            sourceEmail: 'careers@example.com',
            email: 'salma@example.com',
            phone: '+212600000000',
            skills: ['python', 'sql'],
            summary: 'Resume',
            notes: '',
            status: 'new',
            cvUrl: '',
            cvFileName: 'cv.pdf',
          },
        }),
      });
    }

    return Promise.resolve({
      ok: true,
      json: async () => ({
        stats: { totalCandidates: 1, averageScore: 91.5, bestScore: 91.5, newCandidates: 1 },
        profileDistribution: { 'Data Analyst': 1 },
        topCandidates: [
          {
            id: 1,
            fullName: 'Salma Bennani',
            profileLabel: 'Data Analyst',
            matchScore: 91.5,
          },
        ],
        candidates: [
          {
            id: 1,
            fullName: 'Salma Bennani',
            profileLabel: 'Data Analyst',
            matchScore: 91.5,
            summary: 'Resume',
            status: 'new',
            educationLevel: 'Master',
            yearsExperience: 3,
          },
        ],
        jobProfiles: [{ id: 1, name: 'Data Analyst' }],
        filters: {
          statuses: [{ value: 'new', label: 'Nouveau' }],
          profiles: ['Data Analyst'],
        },
      }),
    });
  });

  render(<App />);
  const heading = screen.getByText(/Gestion intelligente et classification automatique des CV/i);
  expect(heading).toBeInTheDocument();
});
