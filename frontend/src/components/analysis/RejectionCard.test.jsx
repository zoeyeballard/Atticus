import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import RejectionCard from "./RejectionCard.jsx";

const props = {
  basis: "103",
  claims: [25, 26, 27],
  references: ["US10,234,567"],
  mappings: [
    { limitation_text: "a processor", mapped_to_reference: "US10,234,567", reference_passage: "col. 4" },
  ],
};

describe("RejectionCard", () => {
  it("renders basis, claims, and references collapsed", () => {
    render(<RejectionCard {...props} />);
    expect(screen.getByText(/Obviousness/)).toBeInTheDocument();
    expect(screen.getByText(/Claims 25, 26, 27/)).toBeInTheDocument();
    // Collapsed: the mapping table is not shown yet.
    expect(screen.queryByText("a processor")).not.toBeInTheDocument();
  });

  it("expands to reveal the claim mapping table on click", () => {
    render(<RejectionCard {...props} />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("a processor")).toBeInTheDocument();
  });
});
