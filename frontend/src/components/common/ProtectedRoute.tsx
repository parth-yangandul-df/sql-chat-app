import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { isAuthenticated } from '../../utils/auth';

export function ProtectedRoute() {
  const location = useLocation();

  if (!isAuthenticated()) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  return <Outlet />;
}
