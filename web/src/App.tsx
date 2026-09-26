import { createBrowserRouter, RouterProvider } from 'react-router'
import { EvidencePage } from './pages/EvidencePage'
import { LandingPage } from './pages/LandingPage'
import { ParcelPage } from './pages/ParcelPage'
import { SearchPage } from './pages/SearchPage'

const router = createBrowserRouter([
  { path: '/', element: <LandingPage /> },
  { path: '/search', element: <SearchPage /> },
  {
    path: '/parcel/:id',
    element: <ParcelPage />,
    children: [{ path: 'evidence/:evidenceId', element: <EvidencePage /> }],
  },
])

export function App() {
  return <RouterProvider router={router} />
}
