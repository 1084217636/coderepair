export const CODE_CHANGE_TEST_PROFILES = [
  { value: "python-pytest", label: "Python / pytest" },
  { value: "go-test", label: "Go / go test ./..." },
  { value: "frontend-check", label: "Frontend / pnpm check" },
] as const;

export type TestProfile = (typeof CODE_CHANGE_TEST_PROFILES)[number]["value"];
