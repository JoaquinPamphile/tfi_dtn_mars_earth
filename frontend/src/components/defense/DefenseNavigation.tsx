import { DefenseControls } from "./DefenseControls";
import styles from "./DefenseNavigation.module.css";

export function DefenseNavigation({
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
}: {
  hasPrevious: boolean;
  hasNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <nav className={styles.nav} aria-label="Recorrido de la defensa">
      <DefenseControls
        hasPrevious={hasPrevious}
        hasNext={hasNext}
        onPrevious={onPrevious}
        onNext={onNext}
      />
    </nav>
  );
}
