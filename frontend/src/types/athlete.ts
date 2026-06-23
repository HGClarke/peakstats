export type AthleteSettings = {
  units: string;
  theme: string;
  default_period: string;
  weekly_goal_m?: number;
};

export type Athlete = {
  id: number;
  name: string;
  avatar_url: string | null;
  settings: AthleteSettings;
};
