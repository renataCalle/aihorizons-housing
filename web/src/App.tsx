import { createBrowserRouter, RouterProvider } from 'react-router'
import { EvidenceDrawer } from './pages/EvidenceDrawer'
import { LandingPage } from './pages/LandingPage'
import { MapScreen } from './pages/MapScreen'
import { ReportView } from './pages/ReportView'
import { ResultsView } from './pages/ResultsView'

const router = createBrowserRouter([
  { path: '/', element: <LandingPage /> },
  {
    // One map for results and reports: it stays mounted while the panels change.
    element: <MapScreen />,
    children: [
      { path: '/search', element: <ResultsView /> },
      {
        path: '/parcel/:id',
        element: <ReportView />,
        children: [{ path: 'evidence/:evidenceId', element: <EvidenceDrawer /> }],
      },
    ],
  },
])

export function App() {
  return <RouterProvider router={router} />
}
