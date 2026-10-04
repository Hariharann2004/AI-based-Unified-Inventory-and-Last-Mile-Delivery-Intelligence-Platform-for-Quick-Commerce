import "@testing-library/jest-dom/vitest";

import { afterEach } from "vitest";
import { cleanup, configure } from "@testing-library/react";

// Coverage workers can contend for CPU; keep asynchronous UI waits bounded.
configure({ asyncUtilTimeout: 3000 });

afterEach(() => cleanup());
