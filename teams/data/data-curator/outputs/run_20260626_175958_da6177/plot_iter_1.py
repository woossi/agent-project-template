import matplotlib.pyplot as plt
import matplotlib as mpl

# Define the output path for the plot
OUTPUT_PATH = "minimal_bar_chart.png"

# Raw Data
categories = ["a", "b", "c"]
values = [1, 2, 3]

# --- Plot Presentation (Aesthetics) Configuration ---
# Set a clean white background for the figure
mpl.rcParams['figure.facecolor'] = '#ffffff'
mpl.rcParams['axes.facecolor'] = '#ffffff'

# Set default font family to sans-serif for consistency
mpl.rcParams['font.family'] = 'sans-serif'
mpl.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans', 'Liberation Sans', 'Bitstream Vera Sans']

# --- Create the plot ---
# Figure Dimensions & Background: aspect ratio 1.6 (e.g., 8x5 inches)
fig, ax = plt.subplots(figsize=(8, 5))

# Plot the bars
# Bar color: distinct blue (#1f77b4)
# Edge color: black (#000000)
# Edge width: 1.0pt
# Bar width: 0.7 units
ax.bar(categories, values, width=0.7, color='#1f77b4', edgecolor='#000000', linewidth=1.0, zorder=2)

# --- Chart Title ---
ax.set_title(
    "Minimal Bar Chart Example",
    fontsize=16,
    fontweight='bold',
    color='#000000',
    loc='center'
)

# --- X-Axis Configuration ---
ax.set_xlabel(
    "Category",
    fontsize=12,
    fontweight='normal',
    color='#000000',
    labelpad=10 # Add some padding between label and ticks
)
ax.tick_params(
    axis='x',
    labelsize=10,
    colors='#000000',
    direction='in', # Inward-facing ticks
    length=4 # Short tick length
)
# Hide top spine, set bottom spine color and width
ax.spines['top'].set_visible(False)
ax.spines['bottom'].set_color('#000000')
ax.spines['bottom'].set_linewidth(1.0)

# --- Y-Axis Configuration ---
ax.set_ylabel(
    "Value",
    fontsize=12,
    fontweight='normal',
    color='#000000',
    labelpad=10 # Add some padding between label and ticks
)
ax.tick_params(
    axis='y',
    labelsize=10,
    colors='#000000',
    direction='in', # Inward-facing ticks
    length=4 # Short tick length
)
# Hide right spine, set left spine color and width
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#000000')
ax.spines['left'].set_linewidth(1.0)

# Set y-axis range from 0 to slightly above the max value (3.0 -> 4.0)
ax.set_ylim(0, 4.0)
# Ensure integer ticks for y-axis if desired, or let matplotlib decide
ax.set_yticks([0, 1, 2, 3])


# --- Grid Configuration ---
# Only horizontal grid lines, behind the bars
ax.grid(
    axis='y',
    color='#cccccc',
    linestyle='--',
    linewidth=0.5,
    zorder=0 # Render behind the bars (default zorder for bars is 1 or higher)
)

# --- Final Touches ---
# Adjust layout to prevent labels/title from overlapping
plt.tight_layout()

# Save the figure to the specified path with high resolution
plt.savefig(OUTPUT_PATH, dpi=300, bbox_inches='tight')

# Close the plot to free up memory
plt.close(fig)