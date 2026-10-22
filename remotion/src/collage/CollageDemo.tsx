import type React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { CardStack } from "./CardStack";
import { Cutout } from "./Cutout";
import { PlateCaptions } from "./PlateCaptions";
import { RedScene } from "./RedScene";

// Демо для проверки компонентов в Studio на пустышках (без контента пользователя).
export const COLLAGE_DEMO_FRAMES = 360;

export const CollageDemo: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: "#000" }}>
    {/* 0–150: стопка карточек, фразы слева сверху */}
    <Sequence from={0} durationInFrames={150}>
      <RedScene stamp="15.8.68">
        <CardStack
          to={150}
          cards={[
            { from: 6, label: "фото 1" },
            { from: 40, label: "скриншот 2" },
            { from: 80, label: "статья 3" },
            { from: 115, label: "афиша 4" },
          ]}
        />
        <PlateCaptions
          position="top-left"
          phrases={[
            { text: "бренд детской одежды", from: 0, to: 60 },
            { text: "выложил фотосессию", from: 60, to: 110, accent: "позировала" },
            { text: "тревогу забили родители", from: 110, to: 150 },
          ]}
        />
      </RedScene>
    </Sequence>

    {/* 150–270: вырезка с рваной обводкой + serif-имя */}
    <Sequence from={150} durationInFrames={120}>
      <RedScene stamp="15.8.68">
        <Cutout src="demo/silhouette.png" from={0} to={120} caption="Имя Фамилия" />
        <PlateCaptions
          position="top-left"
          phrases={[{ text: "и начнём мы с, печально, известной", from: 0, to: 120 }]}
        />
      </RedScene>
    </Sequence>

    {/* 270–360: плашки внизу (как поверх спикера) с акцентом */}
    <Sequence from={270} durationInFrames={90}>
      <AbsoluteFill style={{ background: "linear-gradient(#59575c,#2a2a2e)" }} />
      <PlateCaptions
        phrases={[
          { text: "то и для девочек это тоже", from: 0, to: 45, accent: "ненормально" },
          { text: "давайте разберёмся", from: 45, to: 90 },
        ]}
      />
    </Sequence>
  </AbsoluteFill>
);
