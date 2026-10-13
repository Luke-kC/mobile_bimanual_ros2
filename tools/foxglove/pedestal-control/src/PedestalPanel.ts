import type { PanelExtensionContext } from "@foxglove/extension";
import { ros2humble } from "@foxglove/rosmsg-msgs-common";

// Keep these interfaces synchronized with mobile_bimanual_hardware/pedestal_node.
const TARGET_TOPIC = "/pedestal/position_target";
const JOINT_TOPIC = "/pedestal/joint_states";
const TASK_STATE_TOPIC = "/pedestal/task_state";
const STOP_SERVICE = "/pedestal/stop";
const RESET_FAULT_SERVICE = "/pedestal/reset_fault";
const JOINT_NAME = "pedestal_joint";

const TARGET_SCHEMA = "std_msgs/Float64";
const MIN_POSITION_M = 0;
const MAX_POSITION_M = 0.418; // Verify against calibrated firmware travel limits.

type JointState = { name?: readonly string[]; position?: readonly number[] };
type StringMessage = { data?: string };
type TriggerResponse = { success?: boolean; message?: string };

export function initPedestalPanel(context: PanelExtensionContext): () => void {
  const root = context.panelElement;
  root.innerHTML = `
    <style>
      .pedestal-ui { box-sizing: border-box; font: 14px system-ui, sans-serif;
        color: inherit; padding: 16px; display: grid; gap: 14px; }
      .pedestal-ui * { box-sizing: border-box; }
      .pedestal-ui .pedestal-title { font-size: 16px; font-weight: 700; }
      .pedestal-ui .pedestal-value { font-variant-numeric: tabular-nums; font-weight: 600; }
      .pedestal-ui .pedestal-readout { display: flex; justify-content: space-between;
        align-items: center; gap: 8px; flex-wrap: wrap; }
      .pedestal-ui .pedestal-slider { width: 100%; margin: 5px 0 0; accent-color: #a78bfa; }
      .pedestal-ui .pedestal-limits { display: flex; justify-content: space-between;
        gap: 12px; font-size: 12px; opacity: .8; font-variant-numeric: tabular-nums; }
      .pedestal-ui .pedestal-limits span:last-child { text-align: right; }
      .pedestal-ui .pedestal-buttons { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
      .pedestal-ui button { font: inherit; font-weight: 600; cursor: pointer; padding: 10px;
        border-radius: 6px; border: 1px solid #6b7280; color: #fff; }
      .pedestal-ui button:disabled { opacity: .55; cursor: wait; }
      .pedestal-ui .pedestal-move { background: #4f46e5; }
      .pedestal-ui .pedestal-stop { background: #991b1b; }
      .pedestal-ui .pedestal-reset { background: #6b4f19; }
      @media (max-width: 330px) {
        .pedestal-ui .pedestal-buttons { grid-template-columns: 1fr 1fr; }
        .pedestal-ui .pedestal-reset { grid-column: 1 / -1; }
      }
      .pedestal-ui .pedestal-status { font-size: 13px; line-height: 1.4;
        opacity: .9; overflow-wrap: anywhere; }
    </style>
    <section class="pedestal-ui" aria-label="Pedestal controls">
      <div class="pedestal-title">Pedestal Control</div>
      <div class="pedestal-readout">
        <span>Current position</span>
        <span><span class="pedestal-value" id="pedestal-current">--</span> m</span>
      </div>
      <div class="pedestal-readout">
        <label for="pedestal-target">Target position</label>
        <span><span class="pedestal-value" id="pedestal-target-label">0.100</span> m</span>
      </div>
      <div>
        <input class="pedestal-slider" id="pedestal-target" type="range"
          min="0" max="0.418" step="0.001" value="0.100"
          aria-label="Target pedestal extension (meters)" />
        <div class="pedestal-limits">
          <span>Lower: 0.000 m</span>
          <span>Upper: 0.418 m</span>
        </div>
      </div>
      <div class="pedestal-buttons">
        <button class="pedestal-move" id="pedestal-move" type="button">Move</button>
        <button class="pedestal-stop" id="pedestal-stop" type="button">Stop</button>
        <button class="pedestal-reset" id="pedestal-reset" type="button" title="Reset the pedestal controller fault after resolving its cause">Reset Fault</button>
      </div>
      <div class="pedestal-readout">
        <span>State</span>
        <span class="pedestal-value" id="pedestal-task-state">Waiting for telemetry</span>
      </div>
      <div class="pedestal-status" id="pedestal-feedback" role="status">No command sent</div>
    </section>
  `;

  const select = (selector: string): HTMLElement => {
    const element = root.querySelector<HTMLElement>(selector);
    if (!element) {
      throw new Error(`Missing pedestal control: ${selector}`);
    }
    return element;
  };

  const slider = select("#pedestal-target") as HTMLInputElement;
  const targetLabel = select("#pedestal-target-label");
  const currentLabel = select("#pedestal-current");
  const taskStateLabel = select("#pedestal-task-state");
  const feedbackLabel = select("#pedestal-feedback");
  const moveButton = select("#pedestal-move") as HTMLButtonElement;
  const stopButton = select("#pedestal-stop") as HTMLButtonElement;
  const resetButton = select("#pedestal-reset") as HTMLButtonElement;

  // Updating the slider changes the UI only; it never sends a movement command.
  const onSliderInput = (): void => {
    targetLabel.textContent = Number(slider.value).toFixed(3);
  };
  slider.addEventListener("input", onSliderInput);

  let advertised = false;
  const onMove = (): void => {
    const target = Number(slider.value);
    if (!Number.isFinite(target) || target < MIN_POSITION_M || target > MAX_POSITION_M) {
      feedbackLabel.textContent = "Invalid target position";
      return;
    }
    if (!context.advertise || !context.publish) {
      feedbackLabel.textContent = "Live connection does not support publishing";
      return;
    }
    try {
      if (!advertised) {
        context.advertise(TARGET_TOPIC, TARGET_SCHEMA, {
          datatypes: new Map([[TARGET_SCHEMA, ros2humble[TARGET_SCHEMA]]]),
        });
        advertised = true;
      }
      context.publish(TARGET_TOPIC, { data: target });
      feedbackLabel.textContent = `Move command sent: ${target.toFixed(3)} m`;
    } catch (error) {
      feedbackLabel.textContent = `Move failed: ${String(error)}`;
    }
  };
  moveButton.addEventListener("click", onMove);

  // STOP is a Trigger service, not a topic. Its request is an empty object.
  // It does not depend on the slider or a previous MOVE command.
  const onStop = async (): Promise<void> => {
    if (!context.callService) {
      feedbackLabel.textContent = "Live connection does not support service calls";
      return;
    }
    stopButton.disabled = true;
    feedbackLabel.textContent = "Requesting stop...";
    try {
      const result = (await context.callService(STOP_SERVICE, {})) as TriggerResponse;
      if (result.success !== true) {
        feedbackLabel.textContent = `Stop rejected: ${result.message ?? "unknown reason"}`;
      } else {
        feedbackLabel.textContent = "Stop service responded (verify actual state)";
      }
    } catch (error) {
      feedbackLabel.textContent = `Stop service failed: ${String(error)}`;
    } finally {
      stopButton.disabled = false;
    }
  };
  const handleStopClick = (): void => { void onStop(); };
  stopButton.addEventListener("click", handleStopClick);

  // Fault reset is a distinct Trigger service; it does not command motion.
  // Never disable STOP while a reset request is pending.
  const onResetFault = async (): Promise<void> => {
    if (!context.callService) {
      feedbackLabel.textContent = "Live connection does not support service calls";
      return;
    }
    resetButton.disabled = true;
    feedbackLabel.textContent = "Requesting fault reset...";
    try {
      const result = (await context.callService(RESET_FAULT_SERVICE, {})) as TriggerResponse;
      if (result.success === true) {
        feedbackLabel.textContent = `Fault reset accepted: ${result.message ?? "check live state"}`;
      } else {
        feedbackLabel.textContent = `Fault reset rejected: ${result.message ?? "no successful response"}`;
      }
    } catch (error) {
      feedbackLabel.textContent = `Fault reset failed: ${String(error)}`;
    } finally {
      resetButton.disabled = false;
    }
  };
  const handleResetClick = (): void => { void onResetFault(); };
  resetButton.addEventListener("click", handleResetClick);

  context.subscribe([{ topic: JOINT_TOPIC }, { topic: TASK_STATE_TOPIC }]);
  context.watch("currentFrame");
  context.onRender = (renderState, done) => {
    try {
      for (const event of renderState.currentFrame ?? []) {
        if (event.topic === JOINT_TOPIC) {
          const msg = event.message as JointState;
          const index = msg.name?.indexOf(JOINT_NAME) ?? -1;
          const position = index >= 0 ? msg.position?.[index] : undefined;
          if (position != undefined && Number.isFinite(position)) {
            currentLabel.textContent = position.toFixed(3);
          }
        } else if (event.topic === TASK_STATE_TOPIC) {
          const msg = event.message as StringMessage;
          if (typeof msg.data === "string" && msg.data.length > 0) {
            taskStateLabel.textContent = msg.data;
          }
        }
      }
    } finally {
      done();
    }
  };

  // Destroy subscriptions and event handlers when the panel is removed.
  return () => {
    slider.removeEventListener("input", onSliderInput);
    moveButton.removeEventListener("click", onMove);
    stopButton.removeEventListener("click", handleStopClick);
    resetButton.removeEventListener("click", handleResetClick);
    context.onRender = undefined;
    context.subscribe([]);
    if (advertised) {
      try { context.unadvertise?.(TARGET_TOPIC); } catch { /* May already be disconnected. */ }
    }
    root.replaceChildren();
  };
}
