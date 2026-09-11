import { createAsyncThunk } from "@reduxjs/toolkit";
import { api } from "../api/client";

// Each thunk resolves to { reply, form, risk, tool_calls, userMessage? }.
// Both chatSlice (message log) and complaintSlice (form + risk panel)
// listen to these via extraReducers, so one round-trip keeps the whole UI
// in sync.

export const sendMessage = createAsyncThunk("chat/sendMessage", async (message) => {
  const result = await api.sendMessage(message);
  return { ...result, userMessage: message };
});

export const uploadDocument = createAsyncThunk("chat/uploadDocument", async (file) => {
  const result = await api.uploadDocument(file);
  return { ...result, userMessage: `📄 Uploaded document: ${file.name}` };
});

export const resetSession = createAsyncThunk("chat/resetSession", async () => {
  const result = await api.reset();
  return result;
});

export const loadState = createAsyncThunk("chat/loadState", async () => {
  const result = await api.getState();
  return result;
});