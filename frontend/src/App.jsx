import { useEffect } from "react";
import { useDispatch } from "react-redux";
import ComplaintForm from "./components/ComplaintForm";
import RiskAssessmentPanel from "./components/RiskAssessmentPanel";
import ChatAssistant from "./components/ChatAssistant";
import { loadState } from "./store/thunks";

export default function App() {
  const dispatch = useDispatch();

  useEffect(() => {
    dispatch(loadState());
  }, [dispatch]);

  return (
    <div className="app">
      <header className="app__header">
        <h1>AIVOA — Pharma Complaint QMS</h1>
        <span className="app__tag">AI-assisted complaint intake &amp; risk triage</span>
      </header>

      <main className="app__layout">
        <section className="app__col app__col--form">
          <ComplaintForm />
        </section>
        <section className="app__col app__col--copilot">
          <RiskAssessmentPanel />
          <ChatAssistant />
        </section>
      </main>
    </div>
  );
}