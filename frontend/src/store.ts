import { create } from "zustand";
import type {
  AlgorithmType,
  BankState,
  ScenarioRun,
  SimulationStep,
} from "./types/simulation";

interface SimStore {
  // Selection / controls
  selectedBankId: string | null;
  shockMagnitude: number;
  algorithm: AlgorithmType;
  stepDelayMs: number;

  // Live simulation state
  currentStep: SimulationStep | null;
  bankStateById: Record<string, BankState>;
  isRunning: boolean;
  currentStepIndex: number;

  // History
  history: ScenarioRun[];

  setSelectedBank: (id: string | null) => void;
  setShockMagnitude: (m: number) => void;
  setAlgorithm: (a: AlgorithmType) => void;
  setStepDelay: (d: number) => void;
  setRunning: (r: boolean) => void;
  applyStep: (step: SimulationStep) => void;
  resetSimulation: () => void;
  addHistory: (run: ScenarioRun) => void;
  loadHistory: (run: ScenarioRun) => void;
}

export const useSimStore = create<SimStore>((set) => ({
  selectedBankId: null,
  shockMagnitude: 1.0,
  algorithm: "debtrank",
  stepDelayMs: 800,

  currentStep: null,
  bankStateById: {},
  isRunning: false,
  currentStepIndex: 0,

  history: [],

  setSelectedBank: (id) => set({ selectedBankId: id }),
  setShockMagnitude: (m) => set({ shockMagnitude: m }),
  setAlgorithm: (a) => set({ algorithm: a }),
  setStepDelay: (d) => set({ stepDelayMs: d }),
  setRunning: (r) => set({ isRunning: r }),

  applyStep: (step) =>
    set(() => {
      const map: Record<string, BankState> = {};
      for (const b of step.banks) map[b.id] = b;
      return {
        currentStep: step,
        bankStateById: map,
        currentStepIndex: step.step,
      };
    }),

  resetSimulation: () =>
    set({
      currentStep: null,
      bankStateById: {},
      currentStepIndex: 0,
    }),

  addHistory: (run) => set((s) => ({ history: [run, ...s.history].slice(0, 50) })),

  loadHistory: (run) =>
    set(() => {
      const last = run.steps[run.steps.length - 1];
      const map: Record<string, BankState> = {};
      if (last) for (const b of last.banks) map[b.id] = b;
      return {
        selectedBankId: run.bankId,
        algorithm: run.algorithm,
        shockMagnitude: run.shockMagnitude,
        currentStep: last ?? null,
        bankStateById: map,
        currentStepIndex: last?.step ?? 0,
      };
    }),
}));
