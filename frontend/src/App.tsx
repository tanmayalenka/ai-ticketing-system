import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import UploadPage from "./pages/UploadPage";
import ReviewPage from "./pages/ReviewPage";
import TicketListPage from "./pages/TicketListPage";

export default function App() {
  return (
      <Layout>
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/review/:traceId" element={<ReviewPage />} />
          <Route path="/tickets" element={<TicketListPage />} />
        </Routes>
      </Layout>
  );
}