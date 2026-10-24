import { Fragment } from "react";
import { FlowArrow } from "../scenario/FlowArrow";
import { ScenarioNode } from "../scenario/ScenarioNode";
import type { PlaneNode } from "../../defense/content";
import styles from "./DefenseNodeSequence.module.css";

export function DefenseNodeSequence({ nodes }: { nodes: readonly PlaneNode[] }) {
  return (
    <div className={styles.sequence}>
      {nodes.map((node, index) => (
        <Fragment key={`${node.code}-${node.role}`}>
          {index > 0 ? <FlowArrow size="stage" /> : null}
          <div className={styles.slot}>
            <ScenarioNode size="stage" code={node.code} role={node.role} />
          </div>
        </Fragment>
      ))}
    </div>
  );
}
