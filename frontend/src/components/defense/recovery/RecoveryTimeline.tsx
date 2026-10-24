import { useId } from "react";
import { formatCount } from "../../../domain/metricFormat";
import type { RecoveryEvent, RecoveryPlaybackStep, RecoveryTimelineRun } from "../../../domain/recovery";
import { MILESTONE_LEGEND, MILESTONE_ORDER } from "../../../domain/recovery";
import type { DirectedContact } from "../../../domain/scenario";
import { usePlotSize } from "../../charts/usePlotSize";
import { MilestoneGlyph, MilestoneSwatch } from "./MilestoneGlyph";
import styles from "./recovery.module.css";

export function RecoveryTimeline({
  sender,
  receiver,
  steps,
  activeIndex,
  sameLoss,
  focused,
  domain,
  previousReturn,
  nextReturn,
  onSelect,
}: {
  sender: RecoveryTimelineRun;
  receiver: RecoveryTimelineRun;
  steps: readonly RecoveryPlaybackStep[];
  activeIndex: number;
  sameLoss: boolean;
  focused: boolean;
  domain: { start: number; end: number };
  previousReturn: DirectedContact | null;
  nextReturn: DirectedContact | null;
  onSelect: (index: number) => void;
}) {
  const { ref, width, height } = usePlotSize<HTMLDivElement>();
  const patternId = useId().replace(/:/g, "");
  const active = steps[activeIndex] ?? null;
  const activeIds = new Set(active?.eventIds ?? []);

  return (
    <figure className={styles.timeline} aria-label="Episodio de recuperación de E3, misma escala para ambas políticas">
      <figcaption className={styles.timelineCaption}>
        <span>{focused ? "Vista enfocada del episodio" : "Contexto del escenario"}</span>
        {sameLoss ? <span className={styles.sameLoss}>Misma pérdida silenciosa</span> : null}
      </figcaption>
      <div className={styles.plot} ref={ref}>
        {width > 0 && height > 0 ? (
          <TimelineSvg
            width={width}
            height={height}
            patternId={patternId}
            sender={sender}
            receiver={receiver}
            domain={domain}
            previousReturn={previousReturn}
            nextReturn={nextReturn}
            activeIds={activeIds}
            onSelect={(eventId) => {
              const index = steps.findIndex((step) => step.eventIds.includes(eventId));
              if (index >= 0) {
                onSelect(index);
              }
            }}
          />
        ) : null}
      </div>
      <ul className={styles.legend}>
        {MILESTONE_ORDER.map((kind) => (
          <li key={kind}>
            <MilestoneSwatch kind={kind} />
            <span>{MILESTONE_LEGEND[kind]}</span>
          </li>
        ))}
        <li>
          <i className={styles.laneKey} data-lane="sender" aria-hidden="true" />
          <span>Sender · trazo continuo</span>
        </li>
        <li>
          <i className={styles.laneKey} data-lane="receiver" aria-hidden="true" />
          <span>Receiver · trazo punteado</span>
        </li>
      </ul>
      <table className="srOnly">
        <caption>Hitos almacenados de B y D</caption>
        <thead>
          <tr>
            <th scope="col">Corrida</th>
            <th scope="col">Hito</th>
            <th scope="col">Instante</th>
          </tr>
        </thead>
        <tbody>
          {[...sender.events, ...receiver.events].map((event) => (
            <tr key={event.id}>
              <td>{event.sourceRunLabel}</td>
              <td>{event.label}</td>
              <td>{event.displayTime}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

function TimelineSvg({
  width,
  height,
  patternId,
  sender,
  receiver,
  domain,
  previousReturn,
  nextReturn,
  activeIds,
  onSelect,
}: {
  width: number;
  height: number;
  patternId: string;
  sender: RecoveryTimelineRun;
  receiver: RecoveryTimelineRun;
  domain: { start: number; end: number };
  previousReturn: DirectedContact | null;
  nextReturn: DirectedContact | null;
  activeIds: Set<string>;
  onSelect: (eventId: string) => void;
}) {
  const left = 168;
  const right = 16;
  const top = 18;
  const bottom = 28;
  const plotW = Math.max(1, width - left - right);
  const plotH = Math.max(1, height - top - bottom);
  const laneH = (plotH - 10) / 2;
  const senderY = top + laneH / 2;
  const receiverY = top + laneH + 10 + laneH / 2;
  const xAt = (time: number) => {
    const span = domain.end - domain.start;
    const ratio = span === 0 ? 0 : (time - domain.start) / span;
    return left + ratio * plotW;
  };
  const senderMarks = placed(sender.events, xAt, senderY);
  const receiverMarks = placed(receiver.events, xAt, receiverY);
  const ticks = axisTicks(domain.start, domain.end);

  return (
    <svg width={width} height={height} role="group">
      <defs>
        <pattern id={patternId} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(32)">
          <line x1="0" y1="0" x2="0" y2="6" stroke="var(--bar-return-stripe)" strokeWidth="2" />
        </pattern>
      </defs>
      <Band
        contact={previousReturn}
        label="Retorno previo"
        xAt={xAt}
        top={top}
        height={plotH}
        patternId={patternId}
        variant="previous"
      />
      <Band
        contact={nextReturn}
        label="Próximo retorno"
        xAt={xAt}
        top={top}
        height={plotH}
        patternId={patternId}
        variant="next"
      />
      <line className={styles.laneLine} data-lane="sender" x1={left} x2={left + plotW} y1={senderY} y2={senderY} />
      <line
        className={styles.laneLine}
        data-lane="receiver"
        x1={left}
        x2={left + plotW}
        y1={receiverY}
        y2={receiverY}
      />
      <text className={styles.laneLabel} x={8} y={senderY - 8}>
        {sender.policyLabel} · {sender.label}
      </text>
      <text className={styles.laneHint} x={8} y={senderY + 10}>
        trazo continuo
      </text>
      <text className={styles.laneLabel} x={8} y={receiverY - 8}>
        {receiver.policyLabel} · {receiver.label}
      </text>
      <text className={styles.laneHint} x={8} y={receiverY + 10}>
        trazo punteado
      </text>
      {senderMarks.map((mark) => (
        <Mark key={mark.event.id} mark={mark} active={activeIds.has(mark.event.id)} onSelect={onSelect} />
      ))}
      {receiverMarks.map((mark) => (
        <Mark key={mark.event.id} mark={mark} active={activeIds.has(mark.event.id)} onSelect={onSelect} />
      ))}
      <line className={styles.axis} x1={left} x2={left + plotW} y1={height - 16} y2={height - 16} />
      {ticks.map((tick) => (
        <g key={tick}>
          <line className={styles.tick} x1={xAt(tick)} x2={xAt(tick)} y1={height - 16} y2={height - 12} />
          <text className={styles.tickLabel} x={xAt(tick)} y={height - 2} textAnchor="middle">
            {formatCount(Math.round(tick))} s
          </text>
        </g>
      ))}
    </svg>
  );
}

function Band({
  contact,
  label,
  xAt,
  top,
  height,
  patternId,
  variant,
}: {
  contact: DirectedContact | null;
  label: string;
  xAt: (time: number) => number;
  top: number;
  height: number;
  patternId: string;
  variant: "previous" | "next";
}) {
  if (!contact) {
    return null;
  }
  const x1 = xAt(contact.startSeconds);
  const x2 = xAt(contact.endSeconds);
  const x = Math.min(x1, x2);
  const w = Math.max(2, Math.abs(x2 - x1));
  return (
    <g>
      <rect
        className={styles.band}
        data-variant={variant}
        x={x}
        y={top}
        width={w}
        height={height}
        fill={`url(#${patternId})`}
      />
      <text className={styles.bandLabel} x={x + 4} y={top + 11}>
        {label}
      </text>
    </g>
  );
}

function Mark({
  mark,
  active,
  onSelect,
}: {
  mark: PlacedMark;
  active: boolean;
  onSelect: (eventId: string) => void;
}) {
  return (
    <g
      className={styles.mark}
      data-active={active ? "true" : "false"}
      transform={`translate(${mark.x} ${mark.y})`}
      role="button"
      tabIndex={0}
      aria-label={`${mark.event.label}. ${mark.event.displayTime}. ${mark.event.narrative}`}
      aria-pressed={active}
      onClick={() => onSelect(mark.event.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          onSelect(mark.event.id);
        }
      }}
    >
      <circle className={styles.hit} r={12} />
      {active ? <circle className={styles.activeRing} r={13} /> : null}
      <MilestoneGlyph kind={mark.event.kind} />
    </g>
  );
}

interface PlacedMark {
  event: RecoveryEvent;
  x: number;
  y: number;
}

function placed(events: readonly RecoveryEvent[], xAt: (time: number) => number, laneY: number): PlacedMark[] {
  const occupied: { x: number; slot: number }[] = [];
  return events.map((event) => {
    const x = xAt(event.scientificSeconds);
    let slot = 0;
    while (occupied.some((item) => item.slot === slot && Math.abs(item.x - x) < 18)) {
      slot += 1;
    }
    occupied.push({ x, slot });
    const direction = slot % 2 === 0 ? -1 : 1;
    const offset = Math.ceil(slot / 2) * 16 * direction;
    return { event, x, y: laneY + offset };
  });
}

function axisTicks(start: number, end: number): number[] {
  const span = end - start;
  if (!(span > 0)) {
    return [start];
  }
  const rough = span / 4;
  const exponent = Math.floor(Math.log10(rough));
  const base = 10 ** exponent;
  const fraction = rough / base;
  const nice = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  const step = nice * base;
  const ticks: number[] = [];
  const first = Math.ceil(start / step) * step;
  for (let value = first; value <= end - step * 0.2; value += step) {
    ticks.push(Math.round(value));
  }
  return ticks.length > 0 ? ticks : [Math.round((start + end) / 2)];
}
