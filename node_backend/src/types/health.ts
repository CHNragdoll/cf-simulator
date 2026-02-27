export type ReadyReport = {
  ok: boolean;
  checks: {
    db_readable: boolean;
    state_readable: boolean;
    state_writable: boolean;
    python_upstream: boolean;
  };
  details?: string;
};
