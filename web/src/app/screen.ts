export type ScreenName =
  | 'home'
  | 'playlist'
  | 'search'
  | 'artist'
  | 'artistTracks'
  | 'album'
  | 'volume'
  | 'more';

export type ArtistTracksMode = 'all' | 'familiar';

export type RouteEntry =
  | { screen: 'home' }
  | { screen: 'playlist'; kind: number; title: string; nonce: number }
  | { screen: 'search'; fromHome: boolean }
  | { screen: 'artist'; artistId: number; initialName?: string; nonce: number }
  | { screen: 'artistTracks'; artistId: number; artistName: string; mode: ArtistTracksMode; nonce: number }
  | { screen: 'album'; albumId: number; initialTitle?: string; nonce: number }
  | { screen: 'volume' }
  | { screen: 'more' };

export type PlayerPhase = 'closed' | 'open' | 'closing';
