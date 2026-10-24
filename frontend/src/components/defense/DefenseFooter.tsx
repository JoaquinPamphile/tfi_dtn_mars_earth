import { DefenseNavigation } from "./DefenseNavigation";
import styles from "./DefenseFooter.module.css";

export function DefenseFooter({
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
    <footer className={styles.footer}>
      <DefenseNavigation
        hasPrevious={hasPrevious}
        hasNext={hasNext}
        onPrevious={onPrevious}
        onNext={onNext}
      />
    </footer>
  );
}
