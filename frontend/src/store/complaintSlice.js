import { createSlice } from "@reduxjs/toolkit";
import { sendMessage, uploadDocument, resetSession, loadState } from "./thunks";



const emptyForm = {
  complaint_id: null,
  status: null,
  date_received: null,
  customer_name: null,
  contact_info: null,
  product_name: null,
  product_strength: null,
  batch_number: null,
  manufacturing_date: null,
  expiry_date: null,
  defect_type: null,
  complaint_description: null,
  affected_quantity: null,
  unit: null,
  reported_by: null,
};

const emptyRisk = {
  severity: null,
  regulatory_reportable: null,
  next_action: null,
  root_cause_hint: null,
  capa_suggestion: null,
  rationale: null,
};

const initialState = {
  form: emptyForm,
  risk: emptyRisk,
  completeness: null,
  lastUpdatedFields: [],
};

function diffKeys(oldObj, newObj) {
  return Object.keys(newObj).filter((k) => (oldObj[k] ?? null) !== (newObj[k] ?? null));
}

const complaintSlice = createSlice({
  name: "complaint",
  initialState,
  reducers: {
    clearHighlight(state) {
      state.lastUpdatedFields = [];
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(sendMessage.fulfilled, (state, action) => {
        state.lastUpdatedFields = [
          ...diffKeys(state.form, action.payload.form),
          ...diffKeys(state.risk, action.payload.risk),
        ];
        state.form = action.payload.form;
        state.risk = action.payload.risk;
        state.completeness = action.payload.completeness;
      })
      .addCase(uploadDocument.fulfilled, (state, action) => {
        state.lastUpdatedFields = [
          ...diffKeys(state.form, action.payload.form),
          ...diffKeys(state.risk, action.payload.risk),
        ];
        state.form = action.payload.form;
        state.risk = action.payload.risk;
      })
      .addCase(resetSession.fulfilled, (state, action) => {
        state.form = action.payload.form;
        state.risk = action.payload.risk;
        state.lastUpdatedFields = [];
        state.completeness = null;
      })
      .addCase(loadState.fulfilled, (state, action) => {
        state.form = action.payload.form;
        state.risk = action.payload.risk;
      });
  },
});

export const { clearHighlight } = complaintSlice.actions;
export default complaintSlice.reducer;
