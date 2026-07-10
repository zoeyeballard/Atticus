import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ComingSoonPage from "./ComingSoonPage.jsx";

describe("ComingSoonPage", () => {
  it("renders kicker, title, description, and the in-preparation seal", () => {
    render(
      <ComingSoonPage
        kicker="Research"
        title="Prior Art Search"
        description="Semantic search across indexed patents."
        points={["Point one."]}
      />,
    );
    expect(screen.getByText("Research")).toBeInTheDocument();
    expect(screen.getByText("Prior Art Search")).toBeInTheDocument();
    expect(screen.getByText("Point one.")).toBeInTheDocument();
    expect(screen.getByText(/in preparation/i)).toBeInTheDocument();
  });
});
