import type { RecoveryEventKind } from "../../../domain/recovery";
import styles from "./recovery.module.css";

export function MilestoneGlyph({
  kind,
  size = 8,
}: {
  kind: RecoveryEventKind;
  size?: number;
}) {
  return (
    <g className={styles.glyph} data-kind={kind}>
      {kind === "loss" ? <Cross size={size} /> : null}
      {kind === "gap-observed" ? <GapRing size={size} /> : null}
      {kind === "recovery-trigger" ? <Bolt size={size} /> : null}
      {kind === "recovery-departure" ? <ArrowMark size={size} /> : null}
      {kind === "earth-recovered" ? <CheckedCircle size={size} /> : null}
      {kind === "origin-confirmed" ? <CheckedDiamond size={size} /> : null}
    </g>
  );
}

export function MilestoneSwatch({ kind }: { kind: RecoveryEventKind }) {
  return (
    <svg className={styles.swatch} viewBox="-12 -12 24 24" aria-hidden="true">
      <MilestoneGlyph kind={kind} size={7} />
    </svg>
  );
}

function Cross({ size }: { size: number }) {
  return (
    <>
      <line x1={-size} y1={-size} x2={size} y2={size} />
      <line x1={-size} y1={size} x2={size} y2={-size} />
    </>
  );
}

function GapRing({ size }: { size: number }) {
  return <circle r={size} />;
}

function Bolt({ size }: { size: number }) {
  const s = size / 8;
  return (
    <polygon
      points={`${-1 * s},${-8 * s} ${4 * s},${-1 * s} ${1 * s},${-1 * s} ${3 * s},${8 * s} ${-4 * s},${0} ${-1 * s},${0}`}
    />
  );
}

function ArrowMark({ size }: { size: number }) {
  return (
    <polygon points={`${-size},${-size * 0.7} ${size * 0.2},${0} ${-size},${size * 0.7} ${-size * 0.2},${0}`} />
  );
}

function CheckedCircle({ size }: { size: number }) {
  return (
    <>
      <circle r={size} />
      <Check size={size * 0.62} />
    </>
  );
}

function CheckedDiamond({ size }: { size: number }) {
  return (
    <>
      <polygon points={`0,${-size} ${size},0 0,${size} ${-size},0`} />
      <Check size={size * 0.55} />
    </>
  );
}

function Check({ size }: { size: number }) {
  return <polyline points={`${-size},${0} ${-size * 0.2},${size * 0.8} ${size},${-size * 0.7}`} />;
}
