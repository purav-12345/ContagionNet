import { useCallback, useRef, useState } from "react";
import { WS_URL } from "../lib/api";
import type { AlgorithmType, SimulationStep } from "../types/simulation";

interface UseContagionSocketOptions {
  onStep: (step: SimulationStep) => void;
  onComplete: (steps: SimulationStep[]) => void;
  onError: (error: string) => void;
}

interface SimulationParams {
  bank_id: string;
  shock_magnitude: number;
  algorithm: AlgorithmType;
  step_delay_ms?: number;
}

export function useContagionSocket(options: UseContagionSocketOptions) {
  const [isRunning, setIsRunning] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const stepsRef = useRef<SimulationStep[]>([]);
  const runningRef = useRef(false);
  const optsRef = useRef(options);
  optsRef.current = options;

  const runSimulation = useCallback((params: SimulationParams) => {
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch {
        /* noop */
      }
    }

    stepsRef.current = [];
    setIsRunning(true);
    runningRef.current = true;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      ws.send(JSON.stringify(params));
    };

    ws.onmessage = (event) => {
      const step: SimulationStep = JSON.parse(event.data);

      if (step.error) {
        optsRef.current.onError(step.error);
        setIsRunning(false);
        runningRef.current = false;
        return;
      }

      stepsRef.current.push(step);
      optsRef.current.onStep(step);

      if (step.simulation_complete) {
        setIsRunning(false);
        runningRef.current = false;
        setIsConnected(false);
        optsRef.current.onComplete(stepsRef.current);
      }
    };

    ws.onerror = () => {
      optsRef.current.onError("WebSocket connection failed");
      setIsRunning(false);
      runningRef.current = false;
      setIsConnected(false);
    };

    ws.onclose = () => {
      setIsConnected(false);
      if (runningRef.current) {
        setIsRunning(false);
        runningRef.current = false;
      }
    };
  }, []);

  const stopSimulation = useCallback(() => {
    wsRef.current?.close();
    setIsRunning(false);
    runningRef.current = false;
    setIsConnected(false);
  }, []);

  return { runSimulation, stopSimulation, isRunning, isConnected };
}
