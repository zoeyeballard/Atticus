import { render } from "@testing-library/react";
import { MemoryRouter, Link } from "react-router-dom";
import { describe, it, expect } from "vitest";
import Button from "./Button.jsx";

// Regression guard: Tailwind keeps only class names that appear as complete literals in
// source. If Button ever goes back to constructing `btn-${variant}`, these assertions
// still pass but the safelist in tailwind.config.js is the backstop; together they
// prevent the "white unstyled buttons" purge bug from returning.
describe("Button", () => {
  it("renders the primary variant with its full class literals", () => {
    const { getByText } = render(<Button>Go</Button>);
    const el = getByText("Go");
    expect(el.className).toContain("btn ");
    expect(el.className).toContain("btn-primary");
  });

  it("renders the secondary variant", () => {
    const { getByText } = render(<Button variant="secondary">Alt</Button>);
    expect(getByText("Alt").className).toContain("btn-secondary");
  });

  it("renders as an anchor or router Link when asked", () => {
    const { getByText } = render(
      <MemoryRouter>
        <Button as={Link} to="/x">Nav</Button>
      </MemoryRouter>,
    );
    const el = getByText("Nav");
    expect(el.tagName).toBe("A");
    expect(el.className).toContain("btn-primary");
  });
});
