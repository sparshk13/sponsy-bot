import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router";
import { Shell } from "./components/Shell";
import { Admin } from "./pages/admin/Admin";
import { Dashboard } from "./pages/dashboard/Dashboard";
import { Inbox } from "./pages/inbox/Inbox";
import { Login } from "./pages/login/Login";
import { Memory } from "./pages/memory/Memory";
import { NotFound } from "./pages/notfound/NotFound";
import { Queue } from "./pages/queue/Queue";
import { TargetDetail } from "./pages/targets/TargetDetail";
import { Targets } from "./pages/targets/Targets";
import { Today } from "./pages/today/Today";
import { Usage } from "./pages/usage/Usage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <Shell>
                <Today />
              </Shell>
            }
          />
          <Route
            path="/targets"
            element={
              <Shell>
                <Targets />
              </Shell>
            }
          />
          <Route
            path="/targets/:id"
            element={
              <Shell>
                <TargetDetail />
              </Shell>
            }
          />
          <Route
            path="/queue"
            element={
              <Shell>
                <Queue />
              </Shell>
            }
          />
          <Route
            path="/inbox"
            element={
              <Shell>
                <Inbox />
              </Shell>
            }
          />
          <Route
            path="/dashboard"
            element={
              <Shell>
                <Dashboard />
              </Shell>
            }
          />
          <Route
            path="/memory"
            element={
              <Shell>
                <Memory />
              </Shell>
            }
          />
          <Route
            path="/usage"
            element={
              <Shell>
                <Usage />
              </Shell>
            }
          />

          <Route
            path="/admin"
            element={
              <Shell>
                <Admin />
              </Shell>
            }
          />
          <Route
            path="*"
            element={
              <Shell>
                <NotFound />
              </Shell>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
