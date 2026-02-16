import { colorHash } from "@ctfdio/ctfd-js/ui";
import { mergeObjects } from "../../objects";
import { cumulativeSum } from "../../math";
import dayjs from "dayjs";

export function getOption(mode, places, optionMerge) {
  // Cyberpunk red theme palette for series lines
  const seriesColors = [
    '#ec1313', '#ff4444', '#ff6b35', '#FFD700', '#34C759',
    '#00d4ff', '#5856D6', '#ff2d92', '#C0C0C0', '#FF9500'
  ];

  let option = {
    backgroundColor: 'transparent',
    title: {
      left: "center",
      text: "Top 10 " + (mode === "teams" ? "Teams" : "Users"),
      textStyle: {
        fontFamily: "'Space Grotesk', monospace",
        fontSize: 14,
        fontWeight: 600,
        color: 'rgba(255,255,255,0.85)',
      },
      top: 8,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "cross",
        crossStyle: {
          color: 'rgba(236,19,19,0.3)',
        },
        lineStyle: {
          color: 'rgba(236,19,19,0.4)',
          type: 'dashed',
        },
      },
      backgroundColor: 'rgba(26,10,10,0.95)',
      borderColor: 'rgba(236,19,19,0.3)',
      borderWidth: 1,
      textStyle: {
        fontFamily: "'Space Grotesk', monospace",
        fontSize: 12,
        color: '#fff',
      },
      extraCssText: 'backdrop-filter: blur(12px); border-radius: 8px; box-shadow: 0 8px 32px rgba(0,0,0,0.5);',
    },
    legend: {
      type: "scroll",
      orient: "horizontal",
      align: "left",
      bottom: 35,
      data: [],
      textStyle: {
        fontFamily: "'Space Grotesk', monospace",
        fontSize: 11,
        color: 'rgba(255,255,255,0.6)',
      },
      pageTextStyle: {
        color: 'rgba(255,255,255,0.5)',
      },
      pageIconColor: '#ec1313',
      pageIconInactiveColor: 'rgba(255,255,255,0.2)',
    },
    toolbox: {
      feature: {
        dataZoom: {
          yAxisIndex: "none",
          iconStyle: {
            borderColor: 'rgba(255,255,255,0.4)',
          },
        },
        saveAsImage: {
          iconStyle: {
            borderColor: 'rgba(255,255,255,0.4)',
          },
        },
      },
      right: 16,
      top: 4,
    },
    grid: {
      containLabel: true,
      left: 16,
      right: 16,
      top: 60,
      bottom: 70,
    },
    xAxis: [
      {
        type: "time",
        boundaryGap: false,
        data: [],
        axisLine: {
          lineStyle: {
            color: 'rgba(236,19,19,0.2)',
          },
        },
        axisLabel: {
          fontFamily: "'Space Grotesk', monospace",
          fontSize: 10,
          color: 'rgba(255,255,255,0.4)',
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: 'rgba(236,19,19,0.06)',
            type: 'dashed',
          },
        },
      },
    ],
    yAxis: [
      {
        type: "value",
        axisLine: {
          show: false,
        },
        axisLabel: {
          fontFamily: "'Space Grotesk', monospace",
          fontSize: 10,
          color: 'rgba(255,255,255,0.4)',
        },
        splitLine: {
          lineStyle: {
            color: 'rgba(236,19,19,0.08)',
            type: 'dashed',
          },
        },
      },
    ],
    dataZoom: [
      {
        id: "dataZoomX",
        type: "slider",
        xAxisIndex: [0],
        filterMode: "filter",
        height: 20,
        top: 35,
        borderColor: 'rgba(236,19,19,0.2)',
        fillerColor: 'rgba(236,19,19,0.08)',
        handleStyle: {
          color: '#ec1313',
          borderColor: '#ec1313',
        },
        moveHandleStyle: {
          color: 'rgba(236,19,19,0.3)',
        },
        dataBackground: {
          lineStyle: { color: 'rgba(236,19,19,0.3)' },
          areaStyle: { color: 'rgba(236,19,19,0.05)' },
        },
        selectedDataBackground: {
          lineStyle: { color: '#ec1313' },
          areaStyle: { color: 'rgba(236,19,19,0.15)' },
        },
        textStyle: {
          color: 'rgba(255,255,255,0.5)',
          fontFamily: "'Space Grotesk', monospace",
          fontSize: 10,
        },
      },
    ],
    series: [],
  };

  const teams = Object.keys(places);
  for (let i = 0; i < teams.length; i++) {
    const team_score = [];
    const times = [];
    for (let j = 0; j < places[teams[i]]["solves"].length; j++) {
      team_score.push(places[teams[i]]["solves"][j].value);
      const date = dayjs(places[teams[i]]["solves"][j].date);
      times.push(date.toDate());
    }

    const total_scores = cumulativeSum(team_score);
    let scores = times.map(function (e, i) {
      return [e, total_scores[i]];
    });

    option.legend.data.push(places[teams[i]]["name"]);

    const teamColor = seriesColors[i % seriesColors.length];
    const data = {
      name: places[teams[i]]["name"],
      type: "line",
      smooth: 0.3,
      symbol: 'circle',
      symbolSize: 6,
      label: {
        normal: {
          position: "top",
        },
      },
      lineStyle: {
        width: i === 0 ? 3 : 2,
        color: teamColor,
        shadowColor: teamColor,
        shadowBlur: i === 0 ? 10 : 4,
        shadowOffsetY: 0,
      },
      itemStyle: {
        color: teamColor,
        borderWidth: 2,
        borderColor: teamColor,
        shadowColor: teamColor,
        shadowBlur: 6,
      },
      areaStyle: i < 3 ? {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: teamColor.replace(')', ',0.15)').replace('rgb', 'rgba').replace('#', '') },
            { offset: 1, color: 'rgba(0,0,0,0)' },
          ],
        },
      } : undefined,
      emphasis: {
        lineStyle: {
          width: 4,
          shadowBlur: 16,
        },
        itemStyle: {
          shadowBlur: 12,
          borderWidth: 3,
        },
      },
      data: scores,
    };
    // Fix areaStyle gradient for hex colors
    if (i < 3) {
      data.areaStyle = {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: teamColor + '26' },
            { offset: 1, color: teamColor + '00' },
          ],
        },
      };
    }
    option.series.push(data);
  }

  if (optionMerge) {
    option = mergeObjects(option, optionMerge);
  }
  return option;
}
