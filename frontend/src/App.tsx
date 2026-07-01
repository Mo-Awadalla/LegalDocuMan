import { BrowserRouter as Router, Routes, Route } from "react-router";
import NotFound from "./pages/OtherPage/NotFound";
import AppLayout from "./layout/AppLayout";
import { ScrollToTop } from "./components/common/ScrollToTop";
import Home from "./pages/Dashboard/Home";
import Upload from "./pages/Documents/Upload";
import DocumentsList from "./pages/Documents/DocumentsList";
import DocumentDetail from "./pages/Documents/DocumentDetail";
import ReviewQueue from "./pages/Documents/ReviewQueue";
import TenantSettings from "./pages/Admin/TenantSettings";
import Users from "./pages/Admin/Users";
import Login from "./pages/Auth/Login";
import { AuthProvider } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <ScrollToTop />
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route index path="/" element={<Home />} />
              <Route path="/upload" element={<Upload />} />
              <Route path="/documents" element={<DocumentsList />} />
              <Route path="/documents/review-queue" element={<ReviewQueue />} />
              <Route path="/documents/:id" element={<DocumentDetail />} />
              <Route path="/admin/tenant" element={<TenantSettings />} />
              <Route path="/admin/users" element={<Users />} />
            </Route>
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </Router>
  );
}
