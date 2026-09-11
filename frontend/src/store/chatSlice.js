import { createSlice } from "@reduxjs/toolkit";
import { sendMessage, uploadDocument, resetSession, loadState } from "./thunks";

const initialState = {
  messages: [
    {
      role: "assistant",
      content:
        "Hi, I'm AIVOA Copilot. Describe a customer complaint, upload a complaint PDF/email, or correct a field — I'll fill and update the form for you.",
    },
  ],
  status: "idle", // idle | loading | error
  error: null,
};

const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(sendMessage.pending, (state, action) => {
        state.status = "loading";
        state.error = null;
        state.messages.push({ role: "user", content: action.meta.arg });
      })
      .addCase(sendMessage.fulfilled, (state, action) => {
        state.status = "idle";
        state.messages.push({ role: "assistant", content: action.payload.reply, tool_calls: action.payload.tool_calls });
      })
      .addCase(sendMessage.rejected, (state, action) => {
        state.status = "error";
        state.error = action.error.message;
        state.messages.push({ role: "assistant", content: `⚠️ ${action.error.message}`, isError: true });
      })
      .addCase(uploadDocument.pending, (state, action) => {
        state.status = "loading";
        state.error = null;
        state.messages.push({ role: "user", content: `📄 Uploaded document: ${action.meta.arg.name}` });
      })
      .addCase(uploadDocument.fulfilled, (state, action) => {
        state.status = "idle";
        state.messages.push({ role: "assistant", content: action.payload.reply, tool_calls: action.payload.tool_calls });
      })
      .addCase(uploadDocument.rejected, (state, action) => {
        state.status = "error";
        state.error = action.error.message;
        state.messages.push({ role: "assistant", content: `⚠️ ${action.error.message}`, isError: true });
      })
      .addCase(resetSession.fulfilled, (state) => {
        state.messages = initialState.messages;
        state.status = "idle";
        state.error = null;
      })
      .addCase(loadState.fulfilled, (state, action) => {
        if (action.payload.history?.length) {
          state.messages = action.payload.history.map((t) => ({ role: t.role, content: t.content }));
        }
      });
  },
});

export default chatSlice.reducer;
